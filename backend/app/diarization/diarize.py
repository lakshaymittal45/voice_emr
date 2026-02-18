import os
import json
import torch
import logging
from typing import List, Dict, Optional
from pyannote.audio import Pipeline

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================================================================
# 🔥 DEVICE TOGGLE (MANUAL)
# ================================================================

# ✅ DEFAULT (SAFE FOR INTEL / CPU MACHINES)
DEVICE = torch.device("cpu")

# ------------------------------------------------
# 🚀 WHEN YOU MOVE TO NVIDIA GPU:
# 👉 Uncomment the line below
# ------------------------------------------------
# DEVICE = torch.device("cuda")
# ================================================================

PIPELINE = None
PIPELINE_LOAD_ERROR = None

# ------------------------------------------------------------------
# Load diarization pipeline (singleton with error caching)
# ------------------------------------------------------------------

def load_pipeline():
    global PIPELINE, PIPELINE_LOAD_ERROR

    if PIPELINE_LOAD_ERROR:
        raise RuntimeError(f"Pipeline failed to load previously: {PIPELINE_LOAD_ERROR}")
    
    if PIPELINE is not None:
        return

    logging.info(f"Loading Pyannote diarization pipeline on {DEVICE}...")

    # Check for HuggingFace token
    hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    
    if not hf_token:
        error_msg = (
            "HuggingFace token not found. Set HUGGINGFACE_TOKEN or HF_TOKEN environment variable. "
            "Get token from: https://huggingface.co/settings/tokens"
        )
        PIPELINE_LOAD_ERROR = error_msg
        logging.error(error_msg)
        raise RuntimeError(error_msg)

    try:
        PIPELINE = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )

        PIPELINE.to(DEVICE)
        logging.info("Diarization pipeline loaded successfully")
        
    except Exception as e:
        error_msg = f"Failed to load diarization pipeline: {e}"
        PIPELINE_LOAD_ERROR = error_msg
        logging.error(error_msg)
        raise RuntimeError(error_msg)

# ------------------------------------------------------------------
# Speaker role mapping
# ------------------------------------------------------------------

def map_speakers_to_roles(segments: List[Dict]) -> List[Dict]:
    speaker_order = list(dict.fromkeys(seg["speaker"] for seg in segments))
    role_map = {}

    if len(speaker_order) >= 1:
        role_map[speaker_order[0]] = "Doctor"
    if len(speaker_order) >= 2:
        role_map[speaker_order[1]] = "Patient"

    for seg in segments:
        seg["speaker"] = role_map.get(seg["speaker"], "Unknown")

    return segments

# ------------------------------------------------------------------
# Run diarization
# ------------------------------------------------------------------

def run_diarization(
    audio_path: str,
    min_duration: float = 0.7
) -> List[Dict]:
    """
    Run speaker diarization with robust error handling.
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    load_pipeline()
    logging.info(f"Running diarization on {os.path.basename(audio_path)}")

    # --------------------------------------------------------------
    # 🔥 EARLY EXIT: short audio → skip diarization
    # --------------------------------------------------------------
    try:
        import soundfile as sf
        info = sf.info(audio_path)
    except Exception as e:
        raise RuntimeError(f"Failed to read audio info: {e}")

    if info.duration < 5.0:
        logging.info("Audio too short for diarization, using single speaker fallback.")
        return [{
            "speaker": "Doctor",
            "start": 0.0,
            "end": round(info.duration, 2)
        }]

    # --------------------------------------------------------------
    # Run pyannote directly on file with error handling
    # --------------------------------------------------------------
    try:
        with torch.inference_mode():
            diarization = PIPELINE(audio_path)
    except Exception as e:
        logging.error(f"Diarization failed: {e}")
        # Fallback to single speaker
        logging.warning("Using single speaker fallback due to diarization error")
        return [{
            "speaker": "Doctor",
            "start": 0.0,
            "end": round(info.duration, 2)
        }]

    segments: List[Dict] = []

    for turn, _, speaker in diarization.itertracks(yield_label=True):
        duration = turn.end - turn.start
        if duration >= min_duration:
            segments.append({
                "speaker": speaker,
                "start": round(turn.start, 2),
                "end": round(turn.end, 2)
            })

    if len(segments) < 2:
        logging.warning("Only one speaker detected, using fallback.")
        return [{
            "speaker": "Doctor",
            "start": 0.0,
            "end": round(info.duration, 2)
        }]

    result = map_speakers_to_roles(segments)
    logging.info(f"Diarization completed: {len(result)} segments")
    return result

# ------------------------------------------------------------------
# CLI Testing
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    diarized_segments = run_diarization(sys.argv[1])
    print(json.dumps(diarized_segments, indent=2))
