import os
import json
import logging
import tempfile
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "audio", "recordings")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ------------------------------------------------------------------
# Upload Consultation Audio (ML RUNS ONLY HERE)
# ------------------------------------------------------------------

@app.post("/upload-consultation-audio")
async def upload_consultation_audio(
    patient_id: str,
    clinician: str,
    audio: UploadFile = File(...)
):
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Invalid audio file")

    suffix = os.path.splitext(audio.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=UPLOAD_DIR) as tmp:
        audio_path = tmp.name
        tmp.write(await audio.read())

    logger.info(f"Audio saved: {audio_path}")

    try:
        # 1️⃣ Speaker diarization
        segments = run_diarization(audio_path)

        # 2️⃣ Speaker-wise transcription
        speaker_transcript = speaker_wise_transcription(
            audio_path=audio_path,
            diarization_segments=segments
        )

        if not speaker_transcript:
            raise RuntimeError("Empty speaker-wise transcript")

        # 3️⃣ Clinical note extraction (LLM)
        clinical_notes = extract_clinical_notes(speaker_transcript)

        # 4️⃣ Encrypt speaker-wise transcript JSON
        transcript_json = json.dumps(
            speaker_transcript,
            ensure_ascii=False
        )

        encrypted_transcript = encrypt_text(
            transcript_json,
            AES_KEY
        )

        # 5️⃣ Store in DB (ONLY encrypted text)
        conn = get_mysql_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO audio_records
            (
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
                encrypted_transcript
            )
        )

        audio_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO clinical_notes
            (
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
                clinician,
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
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "audio_id": audio_id,
            "patient_id": patient_id,
            "clinician": clinician
        }

    except Exception as e:
        logger.exception("Upload pipeline failed")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------
# View Consultation (NO ML, DB ONLY)
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
        "SELECT * FROM audio_records WHERE audio_id=%s",
        (audio_id,)
    )
    record = cursor.fetchone()
    cursor.close()
    conn.close()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # 🔓 Decrypt + parse transcript JSON
    decrypted = decrypt_text(
        record["transcript_encrypted"],
        AES_KEY
    )

    speaker_transcript = json.loads(decrypted)

    return {
        "audio_id": audio_id,
        "patient_id": record["patient_id"],
        "clinician": record["handling_clinician"],
        "transcript": speaker_transcript
    }