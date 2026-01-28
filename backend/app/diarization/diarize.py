import os
import json
import torch
import logging
import tempfile
import librosa
import soundfile as sf
from typing import List, Dict
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
# Load diarization pipeline (singleton)
# ------------------------------------------------------------------

def load_pipeline():
    global PIPELINE

    if PIPELINE is not None:
        return

    logging.info("Loading Pyannote diarization pipeline...")

    try:
        PIPELINE = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=True   # requires `huggingface-cli login`
        )
        PIPELINE.to(DEVICE)
        logging.info(f"Diarization pipeline loaded on {DEVICE}")
    except Exception as e:
        PIPELINE = None
        logging.error(f"Failed to load diarization pipeline: {e}")
        raise RuntimeError("Pyannote pipeline could not be loaded")

# ------------------------------------------------------------------
# Speaker role mapping
# ------------------------------------------------------------------

def map_speakers_to_roles(segments: List[Dict]) -> List[Dict]:
    """
    Maps diarization speaker labels to Doctor / Patient.
    Assumes Doctor speaks first (realistic for consultations).
    """

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
    Perform speaker diarization.

    Returns:
    [
      { "speaker": "Doctor", "start": 0.0, "end": 5.2 },
      { "speaker": "Patient", "start": 5.3, "end": 12.1 }
    ]
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    load_pipeline()

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
    # Extract diarization segments
    # --------------------------------------------------------------

    segments: List[Dict] = []

    for turn, _, speaker in diarization.itertracks(yield_label=True):
        duration = turn.end - turn.start
        if duration >= min_duration:
            segments.append({
                "speaker": speaker,
                "start": round(turn.start, 2),
                "end": round(turn.end, 2)
            })

    logging.info(f"Found {len(segments)} diarized segments")

    # --------------------------------------------------------------
    # Validate diarization quality
    # --------------------------------------------------------------

    unique_speakers = set(seg["speaker"] for seg in segments)

    if len(unique_speakers) < 2:
        logging.warning(
            "Diarization detected only ONE speaker. "
            "Audio may be too short or lacks conversational turn-taking."
        )

        # Safe fallback
        total_duration = round(len(audio) / 16000, 2)
        return [{
            "speaker": "Unknown",
            "start": 0.0,
            "end": total_duration
        }]

    # --------------------------------------------------------------
    # Map speaker IDs → Doctor / Patient
    # --------------------------------------------------------------

    segments = map_speakers_to_roles(segments)

    return segments

# ------------------------------------------------------------------
# CLI Testing
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python diarize.py <audio_path>")
        sys.exit(1)

    diarized_segments = run_diarization(sys.argv[1])
    print(json.dumps(diarized_segments, indent=2))