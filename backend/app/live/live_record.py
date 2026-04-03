"""
🎙️ Live Recording WebSocket Handler
Real-time audio streaming with incremental diarization + transcription.
Audio enhancement applied during live capture and on final save.
After recording stops, the full transcript is fed to the LLM pipeline.
"""

import os
import json
import wave
import struct
import asyncio
import logging
import subprocess
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.transcription.transcribe import (
    diarize_and_transcribe_audio,
    enhance_audio_quality,
)
from app.llm.extract_notes import extract_clinical_notes
from app.db.mysql_connection import get_mysql_connection
from app.encryption.aes_encrypt import encrypt_text

logger = logging.getLogger(__name__)

router = APIRouter()

# Same package – always available
from app.config import LIVE_TRANSCRIPT_HOLDBACK_SEC

# ----------------------------------------------------------------
# 📁 Central recordings folder (shared with upload endpoint)
# Configurable via PATIENT_CONVO_DIR env var; defaults to D:\Patient Convo
# ----------------------------------------------------------------
RECORDINGS_DIR = os.getenv("PATIENT_CONVO_DIR", r"D:\Patient Convo")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# How often (in seconds) to run incremental transcription on accumulated audio
# 🔥 Reduced from 15s to 8s for faster real-time feedback
INCREMENTAL_INTERVAL_SEC = 8

# Minimum audio duration (seconds) before attempting incremental transcription
# 🔥 Reduced from 3.0s to 2.0s for quicker initial transcription
MIN_DURATION_FOR_TRANSCRIPTION = 2.0

AES_KEY: Optional[bytes] = None

# ------------------------------------------------------------------
# Check ffmpeg availability at import time
# ------------------------------------------------------------------
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
if not FFMPEG_AVAILABLE:
    logger.warning(
        "⚠️ ffmpeg not found on PATH. Live recording needs ffmpeg for "
        "webm→wav conversion. Install from https://ffmpeg.org"
    )


def _init_aes_key():
    """Lazy-load AES key from env (avoids import-time crash if env isn't set yet)."""
    global AES_KEY
    if AES_KEY is None:
        from dotenv import load_dotenv
        load_dotenv()
        raw = os.getenv("EMR_AES_KEY", "")
        if raw and len(raw.encode("utf-8")) == 32:
            AES_KEY = raw.encode("utf-8")
        else:
            raise RuntimeError("EMR_AES_KEY must be set and exactly 32 bytes")
    return AES_KEY


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _sanitize_id(value: str, max_len: int = 64) -> str:
    """Strip any character that is not alphanumeric, hyphen, or underscore
    and cap length. Prevents path traversal in filenames."""
    import re
    safe = re.sub(r'[^\w\-]', '_', value or 'unknown')
    return safe[:max_len]


def _build_wav_path(patient_id: str) -> str:
    """Return ``<RECORDINGS_DIR>/<patient_id_safe>_<datetime>.wav``."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = _sanitize_id(patient_id)
    filename = f"{safe_id}_{ts}.wav"
    # Extra guard: ensure the resolved path stays inside RECORDINGS_DIR
    candidate = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.abspath(candidate).startswith(os.path.abspath(RECORDINGS_DIR)):
        raise ValueError(f"Path traversal detected for patient_id: {patient_id!r}")
    return candidate


def _save_wav(path: str, pcm_frames: bytes, sample_rate: int = 16000,
              channels: int = 1, sample_width: int = 2):
    """Write raw PCM bytes to a WAV file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_frames)


def _webm_to_wav(webm_bytes: bytes, out_path: str, sample_rate: int = 16000) -> str:
    """Convert raw webm/opus bytes to 16 kHz mono WAV using ffmpeg.

    Raises RuntimeError when conversion fails or the output is empty/invalid.
    """
    if not FFMPEG_AVAILABLE:
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH. "
            "Install from https://ffmpeg.org"
        )

    tmp_webm = out_path + ".tmp.webm"
    try:
        with open(tmp_webm, "wb") as f:
            f.write(webm_bytes)

        logger.info(
            f"🎙️ Converting webm→wav | input={len(webm_bytes)} bytes → {out_path}"
        )

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", tmp_webm,
                "-ar", str(sample_rate),
                "-ac", "1",
                "-sample_fmt", "s16",
                out_path,
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr_msg = result.stderr.decode(errors="replace")[:500]
            logger.error(f"ffmpeg error: {stderr_msg}")
            raise RuntimeError(f"ffmpeg conversion failed: {stderr_msg}")

        # Validate output
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise RuntimeError("ffmpeg produced an empty output file")

        # Quick duration check
        import soundfile as sf
        info = sf.info(out_path)
        logger.info(
            f"✅ WAV written | duration={info.duration:.1f}s | "
            f"rate={info.samplerate} | size={os.path.getsize(out_path)} bytes"
        )

        return out_path
    finally:
        if os.path.exists(tmp_webm):
            os.remove(tmp_webm)


def _enhance_wav(wav_path: str) -> str:
    """Run audio enhancement (noise reduction, normalization, 16 kHz resample)
    on the WAV file IN-PLACE, returning the (possibly new) path.

    Falls back to the original file if enhancement fails.
    """
    try:
        enhanced_path = enhance_audio_quality(wav_path)
        if enhanced_path != wav_path:
            # Replace the original with the enhanced file
            os.replace(enhanced_path, wav_path)
            logger.info(f"✅ Replaced original with enhanced audio: {wav_path}")
        return wav_path
    except Exception as e:
        logger.warning(f"⚠️ Audio enhancement failed, using original: {e}")
        return wav_path


def _segment_identity(seg: Dict) -> tuple:
    return (
        seg.get("speaker"),
        round(float(seg.get("start", 0.0)), 2),
        round(float(seg.get("end", 0.0)), 2),
        seg.get("text", ""),
    )


def _stable_transcript_prefix(transcript: List[Dict], audio_duration: float) -> List[Dict]:
    stable_cutoff = max(0.0, audio_duration - LIVE_TRANSCRIPT_HOLDBACK_SEC)
    return [
        seg for seg in transcript
        if float(seg.get("end", 0.0)) <= stable_cutoff
    ]


def _merge_incremental_transcript(existing: List[Dict], latest_stable: List[Dict]) -> List[Dict]:
    merged = [seg.copy() for seg in existing]

    for seg in latest_stable:
        replaced = False
        for index, previous in enumerate(merged):
            if (
                previous.get("speaker") == seg.get("speaker")
                and abs(float(previous.get("start", 0.0)) - float(seg.get("start", 0.0))) <= 0.6
                and abs(float(previous.get("end", 0.0)) - float(seg.get("end", 0.0))) <= 1.2
            ):
                merged[index] = seg
                replaced = True
                break

        if not replaced:
            merged.append(seg)

    deduped = {}
    for seg in merged:
        deduped[_segment_identity(seg)] = seg

    merged = list(deduped.values())
    merged.sort(key=lambda seg: (float(seg.get("start", 0.0)), float(seg.get("end", 0.0))))
    return merged


async def _send_json(ws: WebSocket, data: dict):
    """Send JSON only if the socket is still open."""
    if ws.client_state == WebSocketState.CONNECTED:
        await ws.send_json(data)


# ------------------------------------------------------------------
# Incremental transcription (runs in a thread so it doesn't block)
# ------------------------------------------------------------------

def _run_incremental_pipeline(wav_path: str) -> List[Dict]:
    """Diarize + transcribe a partial WAV file.

    Audio enhancement is applied automatically since the transcription
    pipeline still routes through ``transcribe_full_audio`` for Whisper.

    Returns speaker transcript list.
    """
    try:
        import soundfile as sf
        info = sf.info(wav_path)
        logger.info(
            f"🎙️ [Incremental] Processing {info.duration:.1f}s of audio | "
            f"Sample rate: {info.samplerate}Hz | Channels: {info.channels}"
        )

        # 1. Run diarization + transcription, overlapping where possible
        segments, transcript = diarize_and_transcribe_audio(wav_path)
        if not segments:
            logger.warning(
                "[Incremental] No diarization segments returned | "
                f"Audio duration: {info.duration:.1f}s | "
                "This may indicate very quiet audio or silence"
            )
            return []

        logger.info(f"[Incremental] Diarization found {len(segments)} speaker segments")
        
        if not transcript:
            logger.warning(
                "[Incremental] Transcription returned no segments | "
                f"Diarization had {len(segments)} segments | "
                "Possible causes: VAD filtered all speech, audio too quiet, or language not detected"
            )
            return []
        
        logger.info(
            f"✅ [Incremental] Got {len(transcript)} transcript segments | "
            f"Total text length: {sum(len(t.get('text', '')) for t in transcript)} chars"
        )
        
        # 🔍 DEBUG: Log first segment for troubleshooting
        if transcript:
            first_seg = transcript[0]
            logger.info(
                f"   First segment: [{first_seg.get('start', 0):.1f}s-{first_seg.get('end', 0):.1f}s] "
                f"Speaker: {first_seg.get('speaker', 'unknown')} | "
                f"Text preview: '{first_seg.get('text', '')[:50]}...'"
            )
        
        return transcript
    except Exception as e:
        logger.error(f"❌ Incremental pipeline error: {type(e).__name__}: {e}", exc_info=True)
        return []


def _run_full_pipeline(
    wav_path: str,
    patient_id: str,
    clinician: str,
) -> int:
    """
    Full pipeline: enhance → diarize/transcribe → LLM → encrypt → DB.
    Returns the audio_id written to MySQL.
    """
    key = _init_aes_key()

    # Validate the saved file
    import soundfile as sf
    info = sf.info(wav_path)
    logger.info(
        f"🎙️ [Live] Full pipeline starting | file={wav_path} | "
        f"duration={info.duration:.1f}s | rate={info.samplerate}"
    )

    if info.duration < 0.5:
        raise RuntimeError(f"Recording too short ({info.duration:.1f}s)")

    # 0. Log file info (enhancement happens inside the transcription pipeline)
    logger.info("🎙️ [Live] Starting full pipeline...")

    # 1. Diarization + transcription (already parallelised internally for Whisper)
    logger.info("🎙️ [Live] Step 1/3: Diarization + Transcription…")
    t0 = time.perf_counter()
    segments, speaker_transcript = diarize_and_transcribe_audio(wav_path)
    if not segments:
        raise RuntimeError("Diarization returned no segments")
    if not speaker_transcript:
        raise RuntimeError("Empty speaker-wise transcript")
    t_dt = time.perf_counter() - t0
    logger.info(f"   → {len(segments)} speaker segs, {len(speaker_transcript)} transcript segs in {t_dt:.1f}s")

    # 2. LLM clinical notes ∥ Encryption  (independent → run concurrently)
    logger.info("🎙️ [Live] Step 2/3: LLM extraction ∥ Encryption (parallel)…")
    t1 = time.perf_counter()

    transcript_json = json.dumps(speaker_transcript, ensure_ascii=False)

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="live_pipe") as pool:
        llm_future = pool.submit(extract_clinical_notes, speaker_transcript)
        encrypt_future = pool.submit(encrypt_text, transcript_json, key)

        clinical_notes = llm_future.result()
        encrypted_transcript = encrypt_future.result()

    t_par = time.perf_counter() - t1
    logger.info(f"   → LLM+Encrypt done in {t_par:.1f}s | chief_complaint={bool(clinical_notes.get('chief_complaint'))}")

    # 3. DB insert (single transaction)
    logger.info("🎙️ [Live] Step 3/3: Saving to database…")
    conn = get_mysql_connection()
    cursor = conn.cursor()
    conn.start_transaction()

    try:
        cursor.execute(
            """
            INSERT INTO audio_records (
                patient_id,
                handling_clinician,
                time_of_capture,
                audio_file_path,
                audio_duration_seconds,
                transcript_encrypted
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                patient_id,
                clinician,
                datetime.now(timezone.utc),
                wav_path,
                round(info.duration, 2),
                encrypted_transcript,
            ),
        )
        audio_id = cursor.lastrowid

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
                clinician,
                clinical_notes.get("chief_complaint"),
                clinical_notes.get("history_of_present_illness"),
                clinical_notes.get("associated_diseases"),
                clinical_notes.get("past_medical_history"),
                clinical_notes.get("drug_history"),
                clinical_notes.get("allergies"),
                clinical_notes.get("assessment"),
                clinical_notes.get("treatment_plan"),
            ),
        )

        conn.commit()
        logger.info(f"✅ [Live] Saved audio_id={audio_id}")
        return audio_id

    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Database transaction failed: {e}")
    finally:
        cursor.close()
        conn.close()


# WebSocket endpoint
# ------------------------------------------------------------------

@router.websocket("/ws/live-record")
async def live_record_ws(ws: WebSocket):
    """
    WebSocket protocol
    ==================
    **Client → Server (binary):** raw audio chunk (webm/opus from MediaRecorder).
    **Client → Server (text/JSON):**
        • ``{"type": "start", "patient_id": "...", "clinician": "..."}``
        • ``{"type": "stop"}``
    **Server → Client (JSON):**
        • ``{"type": "transcript", "data": [...]}``  – incremental transcript
        • ``{"type": "status", "message": "..."}``
        • ``{"type": "done", "audio_id": 123}``
        • ``{"type": "error", "message": "..."}``
        • ``{"type": "connected"}``  – connection confirmed
    """
    await ws.accept()
    logger.info(f"🎙️ Live-record WebSocket connected | Client: {ws.client}")
    
    # Send connection confirmation
    await _send_json(ws, {
        "type": "connected",
        "message": "WebSocket connected successfully"
    })

    patient_id: Optional[str] = None
    clinician: Optional[str] = None
    audio_chunks: bytearray = bytearray()
    recording = False
    wav_path: Optional[str] = None
    incremental_task: Optional[asyncio.Task] = None
    committed_transcript: List[Dict] = []

    # ----------------------------------------------------------
    # Background coroutine: periodic incremental transcription
    # ----------------------------------------------------------
    async def _incremental_loop():
        """Periodically flush accumulated audio to disk & transcribe."""
        nonlocal audio_chunks, wav_path, committed_transcript
        loop = asyncio.get_event_loop()
        cycle = 0

        while recording:
            await asyncio.sleep(INCREMENTAL_INTERVAL_SEC)
            if not recording:
                break
            if len(audio_chunks) == 0:
                continue

            # Send a ping to keep the connection alive
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                break

            cycle += 1
            chunk_size = len(audio_chunks)
            logger.info(
                f"🎙️ [Incremental #{cycle}] {chunk_size} bytes accumulated"
            )

            # Convert accumulated audio to WAV for processing
            tmp_wav = wav_path + f".partial_{cycle}.wav"
            try:
                logger.info(f"[Incremental #{cycle}] Converting {chunk_size} bytes to WAV: {tmp_wav}")
                _webm_to_wav(bytes(audio_chunks), tmp_wav)
                logger.info(f"[Incremental #{cycle}] WAV conversion successful")
            except Exception as e:
                logger.error(f"❌ [Incremental #{cycle}] WAV conversion failed: {type(e).__name__}: {e}", exc_info=True)
                continue

            # Ensure minimum duration
            try:
                import soundfile as sf
                info = sf.info(tmp_wav)
                logger.info(
                    f"[Incremental #{cycle}] WAV file info: duration={info.duration:.2f}s, "
                    f"sample_rate={info.samplerate}Hz, channels={info.channels}, "
                    f"frames={info.frames}, size={os.path.getsize(tmp_wav)} bytes"
                )
                if info.duration < MIN_DURATION_FOR_TRANSCRIPTION:
                    logger.warning(
                        f"[Incremental #{cycle}] Skipped – only {info.duration:.1f}s "
                        f"(need ≥ {MIN_DURATION_FOR_TRANSCRIPTION}s) | "
                        f"Wait for more audio to accumulate"
                    )
                    os.remove(tmp_wav)
                    continue
            except Exception as e:
                logger.error(f"❌ [Incremental #{cycle}] Failed to read WAV info: {e}", exc_info=True)
                if os.path.exists(tmp_wav):
                    os.remove(tmp_wav)
                continue

            # Audio enhancement is handled inside the transcription pipeline
            await _send_json(ws, {"type": "status", "message": "Transcribing…"})
            logger.info(f"[Incremental #{cycle}] Starting diarization + transcription pipeline...")

            try:
                logger.info(f"[Incremental #{cycle}] Running diarization + transcription...")
                transcript = await loop.run_in_executor(
                    None, _run_incremental_pipeline, tmp_wav
                )
                logger.info(f"[Incremental #{cycle}] Pipeline completed, got {len(transcript) if transcript else 0} segments")
                
                if transcript and len(transcript) > 0:
                    stable_transcript = _stable_transcript_prefix(transcript, info.duration)
                    committed_transcript = _merge_incremental_transcript(
                        committed_transcript,
                        stable_transcript,
                    )
                    logger.info(
                        f"✅ [Incremental #{cycle}] SUCCESS! Stable segments this pass: {len(stable_transcript)} | "
                        f"Committed segments: {len(committed_transcript)}"
                    )
                    await _send_json(ws, {
                        "type": "transcript",
                        "data": committed_transcript,
                    })
                    await _send_json(ws, {
                        "type": "status",
                        "message": "🔴 Recording…",
                    })
                else:
                    logger.warning(
                        f"⚠️ [Incremental #{cycle}] No transcript generated | "
                        f"Possible causes:\n"
                        f"  1. Audio too quiet (check microphone volume)\n"
                        f"  2. Only silence/background noise detected\n"
                        f"  3. Diarization found no speakers\n"
                        f"  4. Whisper filtered out all segments (VAD/quality thresholds)\n"
                        f"  5. Language not detected or unsupported\n"
                        f"Check logs above for specific error from diarization or transcription."
                    )
                    # Still send a status update so user knows system is working
                    await _send_json(ws, {
                        "type": "status",
                        "message": "🔴 Recording… (no speech detected yet - speak louder?)",
                    })
            except Exception as e:
                logger.error(
                    f"❌ [Incremental #{cycle}] Pipeline exception: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                await _send_json(ws, {
                    "type": "status",
                    "message": "🔴 Recording… (transcription error - check logs)",
                })
            finally:
                if os.path.exists(tmp_wav):
                    os.remove(tmp_wav)

    # ----------------------------------------------------------
    # Main message loop
    # ----------------------------------------------------------
    try:
        while True:
            message = await ws.receive()

            # --- binary audio chunk ---
            if "bytes" in message and message["bytes"]:
                if recording:
                    audio_chunks.extend(message["bytes"])

            # --- JSON control message ---
            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    await _send_json(ws, {"type": "error", "message": "Invalid JSON"})
                    continue

                msg_type = payload.get("type")

                # -------- START --------
                if msg_type == "start":
                    import re as _re
                    raw_pid = str(payload.get("patient_id") or "unknown")[:100]
                    raw_clin = str(payload.get("clinician") or "system")[:100]
                    # Reject completely blank values
                    if not raw_pid.strip():
                        await _send_json(ws, {"type": "error", "message": "patient_id is required"})
                        continue
                    if not raw_clin.strip():
                        await _send_json(ws, {"type": "error", "message": "clinician is required"})
                        continue
                    # Only store sanitized versions in DB-bound vars;
                    # patient_id is also used in the filename via _build_wav_path which sanitizes.
                    patient_id = raw_pid.strip()
                    clinician = raw_clin.strip()
                    wav_path = _build_wav_path(patient_id)
                    audio_chunks = bytearray()
                    committed_transcript = []
                    recording = True

                    logger.info(
                        f"🎙️ Recording started | Patient: {patient_id} | Clinician: {clinician} | "
                        f"Incremental interval: {INCREMENTAL_INTERVAL_SEC}s"
                    )
                    await _send_json(ws, {
                        "type": "status",
                        "message": f"Recording started (updates every {INCREMENTAL_INTERVAL_SEC}s)",
                    })

                    # Launch incremental transcription loop
                    logger.info(f"🔄 Starting incremental transcription loop (every {INCREMENTAL_INTERVAL_SEC}s)")
                    incremental_task = asyncio.create_task(_incremental_loop())

                # -------- STOP ---------
                elif msg_type == "stop":
                    recording = False

                    if incremental_task:
                        incremental_task.cancel()
                        try:
                            await incremental_task
                        except asyncio.CancelledError:
                            pass

                    if not audio_chunks:
                        await _send_json(ws, {
                            "type": "error",
                            "message": "No audio recorded",
                        })
                        continue

                    logger.info(
                        f"🎙️ [Live] Stop received | "
                        f"{len(audio_chunks)} bytes collected"
                    )

                    # Convert final audio to WAV
                    await _send_json(ws, {
                        "type": "status",
                        "message": "Saving recording…",
                    })
                    try:
                        _webm_to_wav(bytes(audio_chunks), wav_path)
                        logger.info(f"✅ [Live] Audio saved: {wav_path}")
                    except Exception as e:
                        logger.exception(f"Audio conversion failed: {e}")
                        await _send_json(ws, {
                            "type": "error",
                            "message": "Audio conversion failed. Ensure ffmpeg is installed and the recording is valid.",
                        })
                        continue

                    # Audio enhancement is handled inside the transcription pipeline
                    # (no separate _enhance_wav call needed here)

                    # Run full pipeline in thread pool
                    await _send_json(ws, {
                        "type": "status",
                        "message": "Running full analysis (diarization → transcription → clinical notes)…",
                    })

                    loop = asyncio.get_event_loop()
                    try:
                        audio_id = await loop.run_in_executor(
                            None,
                            _run_full_pipeline,
                            wav_path,
                            patient_id,
                            clinician,
                        )
                        await _send_json(ws, {
                            "type": "done",
                            "audio_id": audio_id,
                        })
                        logger.info(
                            f"✅ [Live] Complete! audio_id={audio_id} "
                            f"file={wav_path}"
                        )
                    except Exception as e:
                        logger.exception(f"Full pipeline failed: {e}")
                        await _send_json(ws, {
                            "type": "error",
                            "message": "Processing failed. Please check server logs for details.",
                        })

    except WebSocketDisconnect:
        logger.info("🎙️ Live-record WebSocket disconnected")
        recording = False
        if incremental_task:
            incremental_task.cancel()
        # Save whatever audio we have so nothing is lost
        if audio_chunks and wav_path:
            try:
                _webm_to_wav(bytes(audio_chunks), wav_path)
                logger.info(
                    f"💾 [Live] Saved audio on disconnect: {wav_path} "
                    f"({len(audio_chunks)} bytes)"
                )
            except Exception as e:
                logger.error(f"Failed to save audio on disconnect: {e}")
    except Exception as e:
        logger.exception(f"Live-record WebSocket error: {e}")
        recording = False
        if incremental_task:
            incremental_task.cancel()
        # Save whatever audio we have
        if audio_chunks and wav_path:
            try:
                _webm_to_wav(bytes(audio_chunks), wav_path)
                logger.info(
                    f"💾 [Live] Saved audio on error: {wav_path}"
                )
            except Exception as save_err:
                logger.error(f"Failed to save audio on error: {save_err}")
