import os
import json
import torch
import logging
from typing import List, Dict
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

# ------------------------------------------------------------------
# Load diarization pipeline (singleton)
# ------------------------------------------------------------------

def load_pipeline():
    global PIPELINE

    if PIPELINE is not None:
        return

    logging.info(f"Loading Pyannote diarization pipeline on {DEVICE}...")

    PIPELINE = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=True
    )

    PIPELINE.to(DEVICE)
    logging.info("Diarization pipeline loaded")

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

    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    load_pipeline()
    logging.info(f"Running diarization on {audio_path}")

    # --------------------------------------------------------------
    # 🔥 EARLY EXIT: short audio → skip diarization
    # --------------------------------------------------------------
    import soundfile as sf
    info = sf.info(audio_path)

    if info.duration < 5.0:
        logging.info("Audio too short for diarization, skipping.")
        return [{
            "speaker": "Doctor",
            "start": 0.0,
            "end": round(info.duration, 2)
        }]

    # --------------------------------------------------------------
    # Run pyannote directly on file
    # --------------------------------------------------------------
    with torch.inference_mode():
        diarization = PIPELINE(audio_path)

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

    return map_speakers_to_roles(segments)

# ------------------------------------------------------------------
# CLI Testing
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    diarized_segments = run_diarization(sys.argv[1])
    print(json.dumps(diarized_segments, indent=2))
