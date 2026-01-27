import os
import json
import torch
import logging
import tempfile
import librosa
import soundfile as sf
from pyannote.audio import Pipeline

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

PIPELINE = None

# ------------------------------------------------------------------
# Load diarization pipeline SAFELY
# ------------------------------------------------------------------

def load_pipeline():
    global PIPELINE
    if PIPELINE is not None:
        return

    logging.info("Loading Pyannote diarization pipeline...")

    try:
        PIPELINE = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=True  # ✅ correct way after HF login
        )
        PIPELINE.to(DEVICE)
        logging.info(f"Diarization pipeline loaded on {DEVICE}")
    except Exception as e:
        PIPELINE = None
        logging.error(f"Failed to load diarization pipeline: {e}")
        raise RuntimeError("Pyannote pipeline could not be loaded")

# ------------------------------------------------------------------
# Diarization Function
# ------------------------------------------------------------------

def run_diarization(audio_path: str, min_duration: float = 0.2) -> list:

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    load_pipeline()  # ✅ ensures pipeline is ready

    # --------------------------------------------------------------
    # Preprocess audio (16kHz mono)
    # --------------------------------------------------------------

    audio, _ = librosa.load(audio_path, sr=16000, mono=True)

    if len(audio) < 16000:
        audio = librosa.util.fix_length(audio, size=16000)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, audio, 16000)
        temp_audio_path = tmp.name

    logging.info(f"Running diarization on {audio_path}")

    try:
        with torch.inference_mode():
            diarization = PIPELINE(temp_audio_path)
    finally:
        os.unlink(temp_audio_path)

    # --------------------------------------------------------------
    # Extract segments
    # --------------------------------------------------------------

    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        duration = turn.end - turn.start
        if duration >= min_duration:
            segments.append({
                "speaker": speaker,
                "start": round(turn.start, 2),
                "end": round(turn.end, 2),
            })

    logging.info(f"Found {len(segments)} speaker segments")
    return segments

# ------------------------------------------------------------------
# CLI Testing
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python diarize.py <audio_path>")
        sys.exit(1)

    result = run_diarization(sys.argv[1])
    print(json.dumps(result, indent=2))