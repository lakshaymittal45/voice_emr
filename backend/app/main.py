import os
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import soundfile as sf

# ---------------- INTERNAL IMPORTS ----------------
from app.transcription.offline_indic import hydrate_transcript_variants
from app.transcription.transcribe import diarize_and_transcribe_audio
from app.llm.extract_notes import extract_clinical_notes, _looks_non_clinical_transcript
from app.db.mysql_connection import get_mysql_connection
from app.encryption.aes_encrypt import encrypt_text, decrypt_text
from app.live.live_record import router as live_record_router

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

load_dotenv()

AES_KEY = os.getenv("EMR_AES_KEY")
if not AES_KEY or len(AES_KEY.encode("utf-8")) != 32:
    raise RuntimeError("EMR_AES_KEY must be set and exactly 32 bytes")

AES_KEY = AES_KEY.encode("utf-8")


def _to_utc_iso(dt_value):
    if not dt_value:
        return None
    if getattr(dt_value, "tzinfo", None) is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    else:
        dt_value = dt_value.astimezone(timezone.utc)
    return dt_value.isoformat()

# Custom filter to suppress repetitive status checks from logs
class StatusCheckFilter(logging.Filter):
    def filter(self, record):
        # Suppress GET /consultation-status logs (polled every 3s)
        if 'GET /consultation-status' in record.getMessage():
            return False
        # Suppress GET /processing logs
        if 'GET /processing' in record.getMessage():
            return False
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Apply filter to uvicorn access logger
uvicorn_access = logging.getLogger("uvicorn.access")
uvicorn_access.addFilter(StatusCheckFilter())

# Suppress noisy library warnings
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
warnings.filterwarnings("ignore", category=UserWarning, module="speechbrain")
warnings.filterwarnings("ignore", message=".*_backend.*deprecated.*")

# Reduce verbosity of noisy loggers
logging.getLogger("speechbrain").setLevel(logging.WARNING)
logging.getLogger("pyannote").setLevel(logging.WARNING)
logging.getLogger("torchaudio").setLevel(logging.WARNING)

app = FastAPI(title="Voice EMR Backend")

# CORS: read allowed origins from env var (comma-separated list)
# Example in .env: CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# 🎙️ Live recording WebSocket router
app.include_router(live_record_router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------
# 📁 Central recordings folder
# All patient audio (uploads + live recordings) goes here.
# Configurable via PATIENT_CONVO_DIR env var; defaults to D:\Patient Convo
# ----------------------------------------------------------------
UPLOAD_DIR = os.getenv("PATIENT_CONVO_DIR", r"D:\Patient Convo")
os.makedirs(UPLOAD_DIR, exist_ok=True)
logger.info(f"Patient recordings directory: {UPLOAD_DIR}")

# ------------------------------------------------------------------
# Input validation helpers
# ------------------------------------------------------------------

# Allowed characters for patient_id and clinician: alphanumeric, spaces, hyphens,
# dots, underscores, and common name punctuation.  Max 100 chars.
_IDENT_RE = re.compile(r'^[\w\s\-\.]{1,100}$')

def _validate_identifier(value: str, field_name: str) -> str:
    """Strip, length-check and character-validate a patient/clinician identifier.
    Raises HTTPException 400 on invalid input.
    """
    value = (value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    if len(value) > 100:
        raise HTTPException(status_code=400, detail=f"{field_name} too long (max 100 chars)")
    if not _IDENT_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} contains invalid characters. Use letters, numbers, spaces, hyphens, dots, underscores only."
        )
    return value

# ------------------------------------------------------------------
# Constants for robustness
# ------------------------------------------------------------------
MAX_FILE_SIZE_MB = 1000  # Max audio file size in MB
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}

# Bulk upload limits
MAX_BULK_FILES = 20  # Maximum files in one bulk upload
MAX_BULK_TOTAL_SIZE_MB = 6000  # Maximum total size for bulk upload (2GB)
MAX_BULK_TOTAL_SIZE_BYTES = MAX_BULK_TOTAL_SIZE_MB * 1024 * 1024

# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------

def _build_upload_path(patient_id: str, suffix: str) -> str:
    """
    Build a deterministic file path:
        <UPLOAD_DIR>/<patient_id_safe>_<YYYYMMDD_HHMMSS><suffix>

    If the same patient uploads at the exact same second the file already
    exists and we overwrite it (same recording, no duplicates).
    Different second  →  new file alongside the old one.
    """
    # Sanitize patient_id for use in a filename (spaces → underscores, strip unsafe chars)
    safe_id = re.sub(r'[^\w\-]', '_', patient_id).strip('_') or 'unknown'
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_id}_{ts}{suffix}"
    return os.path.join(UPLOAD_DIR, filename)


def _save_upload(path: str, content: bytes) -> None:
    """Write audio bytes to *path*, overwriting if it already exists."""
    with open(path, "wb") as f:
        f.write(content)


def validate_audio_file(file_path: str) -> Tuple[bool, str]:
    """Validate audio file format and integrity.
    Returns (is_valid, error_message)
    """
    try:
        # Check file exists and has content
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return False, "File is empty or does not exist"
        
        # Validate audio format using soundfile
        info = sf.info(file_path)
        
        # Check minimum duration (at least 0.5 seconds)
        if info.duration < 0.5:
            return False, "Audio duration too short (< 0.5s)"
        
        # Check maximum duration (2 hours)
        if info.duration > 7200:
            return False, "Audio duration too long (> 2 hours)"
        
        return True, ""
    except Exception as e:
        return False, f"Invalid audio format: {str(e)}"

def cleanup_audio_file(file_path: str) -> None:
    """Safely cleanup audio file."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up audio file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup {file_path}: {e}")

# ------------------------------------------------------------------
# 🔥 BACKGROUND ML PIPELINE
# ------------------------------------------------------------------

def process_audio_pipeline(audio_id: int, audio_path: str):
    """
    Runs the FULL ML pipeline asynchronously.
    Always ends in DONE or FAILED state.
    Includes proper resource cleanup and atomic transactions.
    """
    conn = None
    cursor = None

    try:
        logger.info(f"Starting background processing (audio_id={audio_id})")

        # 🔒 Validate audio file before processing
        is_valid, error_msg = validate_audio_file(audio_path)
        if not is_valid:
            raise RuntimeError(f"Audio validation failed: {error_msg}")

        # 1️⃣ + 2️⃣ Diarization and transcription
        logger.info(f"[{audio_id}] Step 1/4: Diarization + Transcription...")
        segments, speaker_transcript = diarize_and_transcribe_audio(audio_path)

        if not segments:
            raise RuntimeError("Diarization returned no segments")

        if not speaker_transcript:
            raise RuntimeError("Empty speaker-wise transcript")

        # 3️⃣ Clinical note extraction
        logger.info(f"[{audio_id}] Step 3/4: LLM extraction...")
        clinical_notes = extract_clinical_notes(speaker_transcript)

        # 4️⃣ Encrypt transcript
        logger.info(f"[{audio_id}] Step 4/4: Encryption & DB storage...")
        encrypted_transcript = encrypt_text(
            json.dumps(speaker_transcript, ensure_ascii=False),
            AES_KEY
        )

        # 5️⃣ Update DB with atomic transaction
        conn = get_mysql_connection()
        cursor = conn.cursor()

        # Start transaction
        conn.start_transaction()

        try:
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
            logger.info(f"✅ Background processing completed (audio_id={audio_id})")

        except Exception as db_error:
            conn.rollback()
            raise RuntimeError(f"Database transaction failed: {db_error}")

    except Exception as e:
        logger.exception(f"❌ Processing failed (audio_id={audio_id}): {e}")

        # 🔥 Mark failure so polling stops - use separate connection
        fail_conn = None
        fail_cursor = None
        try:
            fail_conn = get_mysql_connection()
            fail_cursor = fail_conn.cursor()
            fail_cursor.execute(
                """
                UPDATE audio_records
                SET transcript_encrypted=%s
                WHERE audio_id=%s
                """,
                ("FAILED", audio_id)
            )
            fail_conn.commit()
        except Exception as fail_error:
            logger.exception(f"Failed to mark job as FAILED: {fail_error}")
        finally:
            if fail_cursor:
                fail_cursor.close()
            if fail_conn:
                fail_conn.close()

        # 🧹 Cleanup failed audio file
        cleanup_audio_file(audio_path)

    finally:
        # 🧹 Always cleanup resources
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
    # 🔒 Validation 0: Sanitize identifiers
    patient_id = _validate_identifier(patient_id, "patient_id")
    clinician = _validate_identifier(clinician, "clinician")

    # 🔒 Validation 1: Check filename
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Invalid audio file")

    # 🔒 Validation 2: Check file extension
    suffix = os.path.splitext(audio.filename)[-1].lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported audio format. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )

    # 🔒 Validation 3: Read file with size limit
    audio_content = await audio.read()
    
    if len(audio_content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    
    if len(audio_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB"
        )

    # 🔒 Save file with PatientID_datetime naming (overwrites if same second)
    audio_path = None
    try:
        audio_path = _build_upload_path(patient_id, suffix)
        already_existed = os.path.exists(audio_path)
        _save_upload(audio_path, audio_content)
        logger.info(
            f"Audio {'overwritten' if already_existed else 'saved'}: "
            f"{os.path.basename(audio_path)} ({len(audio_content)} bytes)"
        )

        # 🔒 Validation 4: Verify audio format
        is_valid, error_msg = validate_audio_file(audio_path)
        if not is_valid:
            cleanup_audio_file(audio_path)
            raise HTTPException(status_code=400, detail=error_msg)

        # 🔒 Database insert with proper error handling
        conn = None
        cursor = None
        
        try:
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
                    datetime.now(timezone.utc),
                    audio_path,
                    ""
                )
            )

            audio_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Created audio record {audio_id} for patient {patient_id}")

        except Exception as db_error:
            logger.error(f"Database error during upload: {db_error}")
            cleanup_audio_file(audio_path)
            raise HTTPException(status_code=500, detail="Database error during upload")
        
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        # 🚀 Queue background processing
        background_tasks.add_task(
            process_audio_pipeline,
            audio_id,
            audio_path
        )

        return {
            "status": "accepted",
            "audio_id": audio_id,
            "message": "Audio uploaded successfully and queued for processing"
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during upload: {e}")
        if audio_path:
            cleanup_audio_file(audio_path)
        raise HTTPException(status_code=500, detail="Upload failed")

# ------------------------------------------------------------------
# � Bulk Upload Consultation Audio
# ------------------------------------------------------------------

@app.post("/upload-consultation-audio-bulk")
async def upload_consultation_audio_bulk(
    patient_id: str,
    clinician: str,
    audio_files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # 🔒 Validation 0: Sanitize identifiers
    patient_id = _validate_identifier(patient_id, "patient_id")
    clinician = _validate_identifier(clinician, "clinician")
    """
    Bulk upload multiple consultation audio files.
    All files will be validated and queued for processing.
    Returns list of audio_ids and any per-file errors.
    """
    
    # 🔒 Validation 1: Check number of files
    if not audio_files or len(audio_files) == 0:
        raise HTTPException(status_code=400, detail="No audio files provided")
    
    if len(audio_files) > MAX_BULK_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {MAX_BULK_FILES} files per bulk upload"
        )
    
    logger.info(f"Bulk upload started: {len(audio_files)} files for patient {patient_id}")
    
    results = []
    successful_uploads = []
    failed_uploads = []
    total_size = 0
    
    # First pass: Validate all files and check total size
    for idx, audio in enumerate(audio_files):
        file_num = idx + 1
        
        try:
            # Check filename
            if not audio.filename:
                failed_uploads.append({
                    "file_number": file_num,
                    "filename": "unknown",
                    "status": "rejected",
                    "error": "Invalid filename"
                })
                continue
            
            # Check extension
            suffix = os.path.splitext(audio.filename)[-1].lower()
            if suffix not in ALLOWED_AUDIO_EXTENSIONS:
                failed_uploads.append({
                    "file_number": file_num,
                    "filename": audio.filename,
                    "status": "rejected",
                    "error": f"Unsupported format. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
                })
                continue
            
            # Read file content
            audio_content = await audio.read()
            
            if len(audio_content) == 0:
                failed_uploads.append({
                    "file_number": file_num,
                    "filename": audio.filename,
                    "status": "rejected",
                    "error": "Empty file"
                })
                continue
            
            if len(audio_content) > MAX_FILE_SIZE_BYTES:
                failed_uploads.append({
                    "file_number": file_num,
                    "filename": audio.filename,
                    "status": "rejected",
                    "error": f"File too large. Maximum: {MAX_FILE_SIZE_MB}MB"
                })
                continue
            
            total_size += len(audio_content)
            
            # Store for second pass
            successful_uploads.append({
                "file_number": file_num,
                "filename": audio.filename,
                "suffix": suffix,
                "content": audio_content
            })
            
        except Exception as e:
            logger.error(f"Error validating file {file_num} ({audio.filename}): {e}")
            failed_uploads.append({
                "file_number": file_num,
                "filename": audio.filename or "unknown",
                "status": "rejected",
                "error": f"Validation error: {str(e)}"
            })
    
    # 🔒 Check total size
    if total_size > MAX_BULK_TOTAL_SIZE_BYTES:
        # Cleanup and reject all
        raise HTTPException(
            status_code=413,
            detail=f"Total size too large. Maximum {MAX_BULK_TOTAL_SIZE_MB}MB for bulk upload"
        )
    
    # Second pass: Save files and queue processing
    for file_info in successful_uploads:
        audio_path = None
        
        try:
            # Save file with PatientID_datetime naming (overwrites if same second)
            audio_path = _build_upload_path(patient_id, file_info["suffix"])
            already_existed = os.path.exists(audio_path)
            _save_upload(audio_path, file_info["content"])
            logger.info(
                f"[Bulk {file_info['file_number']}/{len(audio_files)}] "
                f"{'Overwritten' if already_existed else 'Saved'}: "
                f"{os.path.basename(audio_path)} ({len(file_info['content'])} bytes)"
            )
            
            # Validate audio format
            is_valid, error_msg = validate_audio_file(audio_path)
            if not is_valid:
                cleanup_audio_file(audio_path)
                failed_uploads.append({
                    "file_number": file_info["file_number"],
                    "filename": file_info["filename"],
                    "status": "rejected",
                    "error": error_msg
                })
                continue
            
            # Insert into database
            conn = None
            cursor = None
            
            try:
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
                        datetime.now(timezone.utc),
                        audio_path,
                        ""
                    )
                )
                
                audio_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"[Bulk {file_info['file_number']}/{len(audio_files)}] Created record {audio_id}")
                
                # Queue background processing
                background_tasks.add_task(
                    process_audio_pipeline,
                    audio_id,
                    audio_path
                )
                
                results.append({
                    "file_number": file_info["file_number"],
                    "filename": file_info["filename"],
                    "status": "accepted",
                    "audio_id": audio_id
                })
                
            except Exception as db_error:
                logger.error(f"Database error for file {file_info['file_number']}: {db_error}")
                cleanup_audio_file(audio_path)
                failed_uploads.append({
                    "file_number": file_info["file_number"],
                    "filename": file_info["filename"],
                    "status": "rejected",
                    "error": "Database error"
                })
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
        
        except Exception as e:
            logger.exception(f"Error processing file {file_info['file_number']}: {e}")
            if audio_path:
                cleanup_audio_file(audio_path)
            failed_uploads.append({
                "file_number": file_info["file_number"],
                "filename": file_info["filename"],
                "status": "rejected",
                "error": "Processing error"
            })
    
    # Combine results
    all_results = results + failed_uploads
    all_results.sort(key=lambda x: x["file_number"])
    
    success_count = len(results)
    failed_count = len(failed_uploads)
    
    logger.info(
        f"Bulk upload completed: {success_count} successful, "
        f"{failed_count} failed out of {len(audio_files)} files"
    )
    
    return {
        "status": "completed",
        "total_files": len(audio_files),
        "successful": success_count,
        "failed": failed_count,
        "results": all_results
    }

# ------------------------------------------------------------------
# �🔁 Processing Status
# ------------------------------------------------------------------

@app.get("/consultation-status/{audio_id}")
def consultation_status(audio_id: int):
    conn = None
    cursor = None
    try:
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
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Audio not found")

    if row["transcript_encrypted"] == "FAILED":
        return {"audio_id": audio_id, "status": "failed"}

    if not row["transcript_encrypted"]:
        return {"audio_id": audio_id, "status": "processing"}

    return {"audio_id": audio_id, "status": "done"}

# ------------------------------------------------------------------
# 🔁 Batch Processing Status (for bulk uploads)
# ------------------------------------------------------------------

@app.post("/consultation-status-batch")
def consultation_status_batch(audio_ids: list[int]):
    """
    Check status of multiple audio files at once.
    Useful for tracking bulk upload progress.
    """
    
    if not audio_ids:
        raise HTTPException(status_code=400, detail="No audio IDs provided")
    
    if len(audio_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 IDs per batch request")
    
    conn = None
    cursor = None
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        placeholders = ",".join(["%s"] * len(audio_ids))
        cursor.execute(
            f"""
            SELECT audio_id, transcript_encrypted
            FROM audio_records
            WHERE audio_id IN ({placeholders})
            """,
            tuple(audio_ids)
        )
        rows = cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    # Build results
    results = {}
    for row in rows:
        aid = row["audio_id"]
        encrypted = row["transcript_encrypted"]
        
        if encrypted == "FAILED":
            status = "failed"
        elif not encrypted:
            status = "processing"
        else:
            status = "done"
        
        results[aid] = status
    
    # Add "not_found" for missing IDs
    for aid in audio_ids:
        if aid not in results:
            results[aid] = "not_found"
    
    # Calculate summary
    status_counts = {
        "processing": sum(1 for s in results.values() if s == "processing"),
        "done": sum(1 for s in results.values() if s == "done"),
        "failed": sum(1 for s in results.values() if s == "failed"),
        "not_found": sum(1 for s in results.values() if s == "not_found")
    }
    
    return {
        "total": len(audio_ids),
        "summary": status_counts,
        "results": results
    }

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

    conn = None
    cursor = None
    try:
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
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # 🔐 Decrypt transcript
    transcript = []
    encrypted = record["transcript_encrypted"]

    if encrypted and encrypted != "FAILED":
        decrypted = decrypt_text(encrypted, AES_KEY)
        transcript = json.loads(decrypted) if decrypted else []
        if isinstance(transcript, list):
            transcript = hydrate_transcript_variants(transcript)

    clinical_notes = {
        "chief_complaint": record["chief_complaint"],
        "history_of_present_illness": record["history_of_present_illness"],
        "associated_diseases": record["associated_diseases"],
        "past_medical_history": record["past_medical_history"],
        "drug_history": record["drug_history"],
        "allergies": record["allergies"],
        "assessment": record["assessment"],
        "treatment_plan": record["treatment_plan"]
    }

    if isinstance(transcript, list) and _looks_non_clinical_transcript(transcript):
        clinical_notes = {key: None for key in clinical_notes}

    return {
        "audio_id": record["audio_id"],
        "patient_id": record["patient_id"],
        "clinician": record["handling_clinician"],
        "transcript": transcript,
        "clinical_notes": clinical_notes
    }

# ------------------------------------------------------------------
# 🏥 Health Check & System Endpoints
# ------------------------------------------------------------------

@app.get("/health")
def health_check():
    """
    🏥 ENHANCED: Health check endpoint with medical model status.
    Monitors database, storage, encryption, transcription models, and LLM models.
    """
    health_status = {
        "status": "healthy",
        "service": "voice_emr_backend",
        "version": "2.0.0-medical",
        "components": {}
    }
    
    # Check database
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check upload directory
    try:
        if os.path.exists(UPLOAD_DIR) and os.access(UPLOAD_DIR, os.W_OK):
            health_status["components"]["storage"] = "healthy"
        else:
            health_status["components"]["storage"] = "unhealthy: directory not writable"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["storage"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check encryption key
    health_status["components"]["encryption"] = "configured" if AES_KEY else "missing"
    if not AES_KEY:
        health_status["status"] = "unhealthy"
    
    # Check transcription model status
    try:
        from app.transcription.transcribe import get_transcription_status
        transcription_status = get_transcription_status()
        health_status["components"]["transcription"] = {
            "status": "loaded" if transcription_status["active_model"] else "not_loaded",
            "active_model": transcription_status["active_model"],
            "available_models": len(transcription_status["available_models"]),
            "medical_config": transcription_status["medical_config_enabled"]
        }
    except Exception as e:
        health_status["components"]["transcription"] = f"error: {str(e)[:100]}"
        health_status["status"] = "degraded"
    
    # Check LLM model status
    try:
        from app.llm.extract_notes import get_llm_status
        llm_status = get_llm_status()
        health_status["components"]["llm"] = {
            "status": "healthy" if llm_status["ollama_healthy"] else "ollama_unavailable",
            "active_model": llm_status["active_model"],
            "failed_models": len(llm_status["failed_models"]),
            "medical_config": llm_status["medical_config_enabled"]
        }
        if not llm_status["ollama_healthy"]:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["llm"] = f"error: {str(e)[:100]}"
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/models/status")
def get_models_status():
    """
    🏥 NEW: Detailed model status endpoint.
    Returns comprehensive information about all AI models and their capabilities.
    """
    try:
        from app.transcription.transcribe import get_transcription_status
        from app.llm.extract_notes import get_llm_status
        
        transcription_status = get_transcription_status()
        llm_status = get_llm_status()
        
        # Get model configurations
        try:
            from app.config import (
                TRANSCRIPTION_MODELS,
                MEDICAL_LLM_MODELS,
                TRANSCRIPTION_MODEL_PRIORITY,
                MEDICAL_LLM_PRIORITY,
                get_hardware_info
            )
            has_config = True
            hardware_info = get_hardware_info()
        except ImportError:
            has_config = False
            hardware_info = None
        
        response = {
            "medical_config_enabled": has_config,
            "hardware_detection": hardware_info if hardware_info else {"enabled": False},
            "transcription": {
                "active_model": transcription_status["active_model"],
                "loaded_models": transcription_status["available_models"],
                "failed_models": transcription_status["failed_models"],
                "device": transcription_status["device"],
                "auto_fallback": transcription_status["auto_fallback_enabled"],
                "performance_monitoring": transcription_status["performance_monitoring"]
            },
            "llm": {
                "active_model": llm_status["active_model"],
                "ollama_healthy": llm_status["ollama_healthy"],
                "failed_models": llm_status["failed_models"],
                "model_priority": llm_status["model_priority"][:5],  # First 5
                "timeout": llm_status["timeout"],
                "max_retries": llm_status["max_retries"],
                "auto_fallback": llm_status["auto_fallback_enabled"]
            }
        }
        
        # Add model specs if available
        if has_config:
            response["available_transcription_models"] = {
                name: {
                    "params": config["params"],
                    "accuracy": config["accuracy"],
                    "medical_terminology": config["medical_terminology"],
                    "use_case": config["use_case"]
                }
                for name, config in TRANSCRIPTION_MODELS.items()
            }
            
            response["available_llm_models"] = {
                name: {
                    "params": config["params"],
                    "medical_performance": config["medical_performance"],
                    "reasoning": config["reasoning"],
                    "use_case": config["use_case"],
                    "recommended": config["recommended"]
                }
                for name, config in MEDICAL_LLM_MODELS.items()
                if name in MEDICAL_LLM_PRIORITY[:6]  # Top 6 only
            }
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model status: {str(e)}"
        )

@app.get("/patients")
def get_patients():
    """Get list of all patients with their latest appointment info."""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                patient_id,
                MAX(time_of_capture) as last_appointment,
                COUNT(*) as total_appointments,
                MAX(handling_clinician) as last_clinician
            FROM audio_records
            GROUP BY patient_id
            ORDER BY MAX(time_of_capture) DESC
        """
        
        cursor.execute(query)
        patients = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format datetime for JSON
        for patient in patients:
            if patient['last_appointment']:
                patient['last_appointment'] = _to_utc_iso(patient['last_appointment'])
        
        return {
            "status": "success",
            "count": len(patients),
            "patients": patients
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch patients: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

@app.get("/patient/{patient_id}/appointments")
def get_patient_appointments(patient_id: str):
    """Get all appointments/consultations for a specific patient."""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                audio_id,
                patient_id,
                handling_clinician,
                time_of_capture,
                audio_duration_seconds,
                created_at
            FROM audio_records
            WHERE patient_id = %s
            ORDER BY time_of_capture DESC
        """
        
        cursor.execute(query, (patient_id,))
        appointments = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not appointments:
            raise HTTPException(
                status_code=404,
                detail=f"No appointments found for patient: {patient_id}"
            )
        
        # Format datetime for JSON
        for appt in appointments:
            if appt['time_of_capture']:
                appt['time_of_capture'] = _to_utc_iso(appt['time_of_capture'])
            if appt['created_at']:
                appt['created_at'] = _to_utc_iso(appt['created_at'])
        
        return {
            "status": "success",
            "patient_id": patient_id,
            "count": len(appointments),
            "appointments": appointments
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch appointments for {patient_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

@app.get("/")
def root():
    """Root endpoint - API info."""
    return {
        "service": "Voice EMR Backend API",
        "version": "2.0.0-medical",
        "status": "running",
        "enhancements": [
            "medical_grade_transcription",
            "medical_llm_models",
            "automatic_model_fallback",
            "performance_monitoring"
        ],
        "features": ["live_recording", "single_upload", "bulk_upload", "batch_status", "patient_search", "model_status"],
        "endpoints": {
            "live_record_ws": "/ws/live-record",
            "single_upload": "/upload-consultation-audio",
            "bulk_upload": "/upload-consultation-audio-bulk",
            "status": "/consultation-status/{audio_id}",
            "batch_status": "/consultation-status-batch",
            "retrieve": "/consultation/{audio_id}",
            "patients": "/patients",
            "patient_appointments": "/patient/{patient_id}/appointments",
            "health": "/health",
            "models_status": "/models/status"
        },
        "limits": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "max_bulk_files": MAX_BULK_FILES,
            "max_bulk_total_size_mb": MAX_BULK_TOTAL_SIZE_MB,
            "allowed_formats": list(ALLOWED_AUDIO_EXTENSIONS)
        },
        "ai_models": {
            "transcription": "Whisper (large-v3 > medium >small) with auto-fallback",
            "llm": "Medical LLMs (llama3.1:70b > mixtral:8x7b > ...)",
            "diarization": "PyAnnote Audio 3.1.1"
        }
    }

# ------------------------------------------------------------------
# 🛑 Graceful Shutdown Handler
# ------------------------------------------------------------------

@app.on_event("shutdown")
def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down Voice EMR Backend...")
    
    try:
        from app.db.mysql_connection import close_connection_pool
        close_connection_pool()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
