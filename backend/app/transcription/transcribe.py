import os
import logging
import soundfile as sf
from typing import List, Dict
from faster_whisper import WhisperModel

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================================================================
# 🔥 MODEL CONFIG (CPU SAFE)
# ================================================================
MODEL_NAME = "medium"          # 🔥 medium is TOO SLOW on CPU
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
# ================================================================

logging.info(
    f"Loading Faster-Whisper model ({MODEL_NAME}) "
    f"on {DEVICE.upper()} with {COMPUTE_TYPE}..."
)

WHISPER_MODEL = WhisperModel(
    MODEL_NAME,
    device=DEVICE,
    compute_type=COMPUTE_TYPE
)

logging.info("Faster-Whisper model loaded")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def map_speaker_label(label: str) -> str:
    label = label.lower()
    if label == "doctor":
        return "Doctor"
    if label == "patient":
        return "Patient"
    return "Unknown"


def estimate_confidence(text: str) -> float:
    if not text:
        return 0.0

    words = len(text.split())
    if words <= 3:
        return 0.75
    if words <= 8:
        return 0.82
    return round(min(0.95, 0.82 + words / 120), 2)

# ------------------------------------------------------------------
# Transcribe FULL audio ONCE (FAST + SAFE)
# ------------------------------------------------------------------

def transcribe_full_audio(audio_path: str):
    """
    CPU-safe Whisper transcription.
    - No word timestamps (FAST)
    - No context chaining (SAFE)
    - VAD only for longer audio
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    duration = sf.info(audio_path).duration
    use_vad = duration > 15.0

    logging.info(
        f"Starting Whisper transcription | "
        f"duration={duration:.2f}s | VAD={'ON' if use_vad else 'OFF'}"
    )

    segments, info = WHISPER_MODEL.transcribe(
        audio_path,
        language=None,

        # 🔥 CPU-OPTIMIZED SETTINGS
        beam_size=4,
        best_of=4,
        temperature=0.0,

        condition_on_previous_text=False,
        word_timestamps=False,

        vad_filter=use_vad,
        vad_parameters={"min_silence_duration_ms": 900} if use_vad else None,
    )

    logging.info(
        f"Whisper detected language={info.language} "
        f"(prob={info.language_probability:.2f})"
    )

    return list(segments)

# ------------------------------------------------------------------
# Speaker-wise transcription (ROBUST)
# ------------------------------------------------------------------

def speaker_wise_transcription(
    audio_path: str,
    diarization_segments: List[Dict]
) -> List[Dict]:

    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    # 🔥 SAFETY NET: empty diarization
    if not diarization_segments:
        logging.warning("Empty diarization segments → fallback to whole audio")
        diarization_segments = [{
            "speaker": "Unknown",
            "start": 0.0,
            "end": sf.info(audio_path).duration
        }]

    logging.info("Starting full-audio Whisper transcription")
    whisper_segments = transcribe_full_audio(audio_path)
    logging.info("Whisper transcription finished")

    results = []

    for dseg in diarization_segments:
        d_start = dseg["start"]
        d_end = dseg["end"]
        speaker = map_speaker_label(dseg["speaker"])

        texts = []

        for wseg in whisper_segments:
            # 🔥 Overlap-based alignment (SAFE)
            if wseg.end > d_start and wseg.start < d_end:
                texts.append(wseg.text.strip())

        final_text = " ".join(texts).strip()
        if not final_text:
            continue

        results.append({
            "speaker": speaker,
            "start": round(d_start, 2),
            "end": round(d_end, 2),
            "text": final_text,
            "confidence": estimate_confidence(final_text)
        })

    logging.info(
        f"Speaker-wise transcription completed | "
        f"segments={len(results)}"
    )

    return results
