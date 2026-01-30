import os
import json
import logging
import tempfile
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ---------------- INTERNAL IMPORTS ----------------
from app.diarization.diarize import run_diarization
from app.transcription.transcribe import speaker_wise_transcription
from app.llm.extract_notes import extract_clinical_notes
from app.db.mysql_connection import get_mysql_connection
from app.encryption.aes_encrypt import encrypt_text, decrypt_text

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

load_dotenv()

AES_KEY = os.getenv("EMR_AES_KEY")
if not AES_KEY or len(AES_KEY.encode("utf-8")) != 32:
    raise RuntimeError("EMR_AES_KEY must be set and exactly 32 bytes")

AES_KEY = AES_KEY.encode("utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice EMR Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "audio", "recordings")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ------------------------------------------------------------------
# 🔥 BACKGROUND ML PIPELINE
# ------------------------------------------------------------------

def process_audio_pipeline(audio_id: int, audio_path: str):
    """
    Runs the FULL ML pipeline asynchronously.
    Always ends in DONE or FAILED state.
    """
    conn = None
    cursor = None

    try:
        logger.info(f"Starting background processing (audio_id={audio_id})")

        # 1️⃣ Diarization
        segments = run_diarization(audio_path)

        # 2️⃣ Transcription
        speaker_transcript = speaker_wise_transcription(
            audio_path=audio_path,
            diarization_segments=segments
        )

        if not speaker_transcript:
            raise RuntimeError("Empty speaker-wise transcript")

        # 3️⃣ Clinical note extraction
        clinical_notes = extract_clinical_notes(speaker_transcript)

        # 4️⃣ Encrypt transcript
        encrypted_transcript = encrypt_text(
            json.dumps(speaker_transcript, ensure_ascii=False),
            AES_KEY
        )

        # 5️⃣ Update DB
        conn = get_mysql_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE audio_records
            SET transcript_encrypted=%s
            WHERE audio_id=%s
            """,
            (encrypted_transcript, audio_id)
        )

        cursor.execute(
            """
            INSERT INTO clinical_notes (
                audio_id,
                handling_clinician,
                chief_complaint,
                history_of_present_illness,
                associated_diseases,
                past_medical_history,
                drug_history,
                allergies,
                assessment,
                treatment_plan
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                audio_id,
                "system",
                clinical_notes.get("chief_complaint"),
                clinical_notes.get("history_of_present_illness"),
                clinical_notes.get("associated_diseases"),
                clinical_notes.get("past_medical_history"),
                clinical_notes.get("drug_history"),
                clinical_notes.get("allergies"),
                clinical_notes.get("assessment"),
                clinical_notes.get("treatment_plan"),
            )
        )

        conn.commit()
        logger.info(f"Background processing completed (audio_id={audio_id})")

    except Exception:
        logger.exception(f"❌ Processing failed (audio_id={audio_id})")

        # 🔥 Mark failure so polling stops
        try:
            conn = conn or get_mysql_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE audio_records
                SET transcript_encrypted=%s
                WHERE audio_id=%s
                """,
                ("FAILED", audio_id)
            )
            conn.commit()
        except Exception:
            logger.exception("Failed to mark job as FAILED")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ------------------------------------------------------------------
# 📤 Upload Consultation Audio
# ------------------------------------------------------------------

@app.post("/upload-consultation-audio")
async def upload_consultation_audio(
    patient_id: str,
    clinician: str,
    audio: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Invalid audio file")

    suffix = os.path.splitext(audio.filename)[-1]

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        dir=UPLOAD_DIR
    ) as tmp:
        audio_path = tmp.name
        tmp.write(await audio.read())

    logger.info(f"Audio saved at {audio_path}")

    conn = get_mysql_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO audio_records (
            patient_id,
            handling_clinician,
            time_of_capture,
            audio_file_path,
            transcript_encrypted
        )
        VALUES (%s,%s,%s,%s,%s)
        """,
        (
            patient_id,
            clinician,
            datetime.utcnow(),
            os.path.basename(audio_path),
            ""
        )
    )

    audio_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    background_tasks.add_task(
        process_audio_pipeline,
        audio_id,
        audio_path
    )

    return {
        "status": "accepted",
        "audio_id": audio_id
    }

# ------------------------------------------------------------------
# 🔁 Processing Status
# ------------------------------------------------------------------

@app.get("/consultation-status/{audio_id}")
def consultation_status(audio_id: int):
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT transcript_encrypted
        FROM audio_records
        WHERE audio_id=%s
        """,
        (audio_id,)
    )
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Audio not found")

    if row["transcript_encrypted"] == "FAILED":
        return {"audio_id": audio_id, "status": "failed"}

    if not row["transcript_encrypted"]:
        return {"audio_id": audio_id, "status": "processing"}

    return {"audio_id": audio_id, "status": "done"}

# ------------------------------------------------------------------
# 📄 View Consultation (Transcript + Clinical Notes)
# ------------------------------------------------------------------

@app.get("/consultation/{audio_id}")
async def get_consultation(
    audio_id: int,
    role: str = Query(...)
):
    if role not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT 
            ar.audio_id,
            ar.patient_id,
            ar.handling_clinician,
            ar.transcript_encrypted,

            cn.chief_complaint,
            cn.history_of_present_illness,
            cn.associated_diseases,
            cn.past_medical_history,
            cn.drug_history,
            cn.allergies,
            cn.assessment,
            cn.treatment_plan

        FROM audio_records ar
        LEFT JOIN clinical_notes cn
            ON ar.audio_id = cn.audio_id
        WHERE ar.audio_id = %s
        """,
        (audio_id,)
    )

    record = cursor.fetchone()
    cursor.close()
    conn.close()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # 🔐 Decrypt transcript
    transcript = []
    encrypted = record["transcript_encrypted"]

    if encrypted and encrypted != "FAILED":
        decrypted = decrypt_text(encrypted, AES_KEY)
        transcript = json.loads(decrypted) if decrypted else []

    return {
        "audio_id": record["audio_id"],
        "patient_id": record["patient_id"],
        "clinician": record["handling_clinician"],
        "transcript": transcript,
        "clinical_notes": {
            "chief_complaint": record["chief_complaint"],
            "history_of_present_illness": record["history_of_present_illness"],
            "associated_diseases": record["associated_diseases"],
            "past_medical_history": record["past_medical_history"],
            "drug_history": record["drug_history"],
            "allergies": record["allergies"],
            "assessment": record["assessment"],
            "treatment_plan": record["treatment_plan"]
        }
    }
