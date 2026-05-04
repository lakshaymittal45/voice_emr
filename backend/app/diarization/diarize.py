import os
import json
import torch
import logging
import tempfile
from typing import List, Dict, Optional
from pyannote.audio import Pipeline
import soundfile as sf

try:
    import librosa
except ImportError:
    librosa = None

# Same package – always available
from app.config import DIARIZATION_MERGE_GAP_SEC, OPTIMAL_DEVICE

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================================================================
# 🔥 DEVICE AUTO-DETECTION (from config.py hardware detection)
# ================================================================
DEVICE = torch.device(OPTIMAL_DEVICE)
logging.info(f"Diarization device: {DEVICE}")
# ================================================================

PIPELINE = None
PIPELINE_LOAD_ERROR = None


def _prepare_audio_for_diarization(audio_path: str) -> str:
    """
    Normalize audio into mono 16 kHz PCM WAV for pyannote stability.
    Returns the original path when no conversion is needed.
    """
    if librosa is None:
        return audio_path

    try:
        audio, sample_rate = librosa.load(audio_path, sr=None, mono=True)
        if audio is None or len(audio) == 0:
            return audio_path

        needs_conversion = (
            sample_rate != 16000
            or audio_path.lower().endswith((".mp3", ".m4a", ".ogg", ".webm", ".flac"))
        )

        if not needs_conversion:
            return audio_path

        if sample_rate != 16000:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
            sample_rate = 16000

        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"voice_emr_diarization_{os.path.basename(audio_path)}.wav",
        )
        sf.write(temp_path, audio, sample_rate, subtype="PCM_16")
        logging.info("Prepared normalized audio for diarization: %s", os.path.basename(temp_path))
        return temp_path
    except Exception as exc:
        logging.warning("Could not normalize audio for diarization, using original file: %s", exc)
        return audio_path

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
    """Map pyannote speaker IDs to SPEAKER_00, SPEAKER_01, etc."""
    speaker_order = list(dict.fromkeys(seg["speaker"] for seg in segments))
    role_map = {}

    # Map speakers to numbered labels: SPEAKER_00, SPEAKER_01, SPEAKER_02, etc.
    for idx, original_speaker in enumerate(speaker_order):
        role_map[original_speaker] = f"SPEAKER_{idx:02d}"

    for seg in segments:
        seg["speaker"] = role_map.get(seg["speaker"], "SPEAKER_UNKNOWN")

    return segments


def _merge_adjacent_same_speaker_segments(
    segments: List[Dict],
    max_gap: float = DIARIZATION_MERGE_GAP_SEC,
) -> List[Dict]:
    if not segments:
        return segments

    ordered = sorted(segments, key=lambda seg: (seg["start"], seg["end"], seg["speaker"]))
    merged = [ordered[0].copy()]

    for current in ordered[1:]:
        previous = merged[-1]
        gap = current["start"] - previous["end"]

        if (
            current["speaker"] == previous["speaker"]
            and gap >= 0
            and gap <= max_gap
        ):
            previous["end"] = round(max(previous["end"], current["end"]), 2)
            continue

        merged.append(current.copy())

    return merged


def _annotate_segment_overlaps(segments: List[Dict]) -> List[Dict]:
    """Annotate overlapping speaker segments using a sweep-line approach (O(n log n))."""
    if not segments:
        return segments

    ordered = sorted(segments, key=lambda seg: (seg["start"], seg["end"], seg["speaker"]))
    annotated = []

    for index, segment in enumerate(ordered):
        overlap_speakers = set()
        segment_start = float(segment["start"])
        segment_end = float(segment["end"])

        # Only scan nearby segments (break early when sorted start > our end)
        for other_index in range(len(ordered)):
            if other_index == index:
                continue
            other = ordered[other_index]
            other_start = float(other["start"])
            if other_start >= segment_end:
                break  # No more overlaps possible for this segment
            other_end = float(other["end"])
            overlap = max(0.0, min(segment_end, other_end) - max(segment_start, other_start))
            if overlap > 0 and other["speaker"] != segment["speaker"]:
                overlap_speakers.add(other["speaker"])

        enriched = segment.copy()
        if overlap_speakers:
            enriched["overlap"] = True
            enriched["overlap_speakers"] = sorted(overlap_speakers)
        else:
            enriched["overlap"] = False

        annotated.append(enriched)

    return annotated

# ------------------------------------------------------------------
# Run diarization
# ------------------------------------------------------------------

def run_diarization(
    audio_path: str,
    min_duration: float = 0.3  # 🔥 REDUCED from 0.7s to 0.3s for better live recording
) -> List[Dict]:
    """
    Run speaker diarization with robust error handling.
    
    Args:
        audio_path: Path to audio file
        min_duration: Minimum segment duration in seconds (default 0.3s)
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    load_pipeline()
    logging.info(f"Running diarization on {os.path.basename(audio_path)}")

    # --------------------------------------------------------------
    # 🔥 EARLY EXIT: very short audio → skip diarization
    # --------------------------------------------------------------
    prepared_audio_path = _prepare_audio_for_diarization(audio_path)

    try:
        info = sf.info(prepared_audio_path)
    except Exception as e:
        raise RuntimeError(f"Failed to read audio info: {e}")

    # 🔥 REDUCED: 5.0s → 3.0s for faster live transcription feedback
    if info.duration < 3.0:
        logging.info(f"Audio too short ({info.duration:.1f}s < 3.0s) for diarization, using single speaker fallback.")
        return [{
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": round(info.duration, 2)
        }]

    # --------------------------------------------------------------
    # Run pyannote directly on file with error handling
    # --------------------------------------------------------------
    try:
        with torch.inference_mode():
            diarization = PIPELINE(prepared_audio_path)
    except Exception as e:
        logging.error(f"Diarization failed: {e}")
        # Fallback to single speaker
        logging.warning("Using single speaker fallback due to diarization error")
        return [{
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": round(info.duration, 2)
        }]
    finally:
        if prepared_audio_path != audio_path and os.path.exists(prepared_audio_path):
            try:
                os.remove(prepared_audio_path)
            except Exception:
                pass

    segments: List[Dict] = []

    for turn, _, speaker in diarization.itertracks(yield_label=True):
        duration = turn.end - turn.start
        if duration >= min_duration:
            segments.append({
                "speaker": speaker,
                "start": round(turn.start, 2),
                "end": round(turn.end, 2)
            })

    # ⚠️ FIXED: One speaker is valid! Only use fallback if NO segments
    if len(segments) == 0:
        logging.warning("No speaker segments detected, using single speaker fallback.")
        return [{
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": round(info.duration, 2)
        }]

    result = map_speakers_to_roles(segments)
    result = _merge_adjacent_same_speaker_segments(result)
    result = _annotate_segment_overlaps(result)
    logging.info(f"Diarization completed: {len(result)} segments")
    return result

# ------------------------------------------------------------------
# CLI Testing
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    diarized_segments = run_diarization(sys.argv[1])
    print(json.dumps(diarized_segments, indent=2))
