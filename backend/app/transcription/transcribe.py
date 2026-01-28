# import os
# import torch
# import whisper
# import librosa
# import tempfile
# import soundfile as sf
# import logging
# from typing import List, Dict

# from indic_transliteration import sanscript
# from indic_transliteration.sanscript import transliterate

# # ------------------------------------------------------------------
# # Setup
# # ------------------------------------------------------------------

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)s | %(message)s"
# )

# DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# MODEL_NAME = "medium"

# logging.info(f"Loading Whisper model ({MODEL_NAME}) on {DEVICE}...")
# WHISPER_MODEL = whisper.load_model(MODEL_NAME, device=DEVICE)
# logging.info("Whisper model loaded")

# # ------------------------------------------------------------------
# # Helpers
# # ------------------------------------------------------------------

# def transliterate_hindi_only(text: str) -> str:
#     """
#     Transliterate ONLY Devanagari (Hindi) characters → Roman.
#     Leaves English / Spanish untouched.
#     """
#     try:
#         return transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
#     except Exception:
#         return text


# def map_speaker_label(label: str) -> str:
#     """
#     Map pyannote speaker labels → human readable roles.
#     """
#     if label == "SPEAKER_00":
#         return "Doctor"
#     if label == "SPEAKER_01":
#         return "Patient"
#     return label


# def estimate_confidence(text: str) -> float:
#     """
#     Simple heuristic confidence score.
#     (Whisper does not expose true confidence)
#     """
#     if not text:
#         return 0.0
#     length = len(text.split())
#     return min(0.95, 0.6 + (length / 50))


# # ------------------------------------------------------------------
# # Core transcription
# # ------------------------------------------------------------------

# def transcribe_audio(audio_path: str) -> str:
#     if not os.path.exists(audio_path):
#         raise FileNotFoundError(f"Audio file not found: {audio_path}")

#     audio, _ = librosa.load(audio_path, sr=16000, mono=True)

#     if len(audio) < 16000:
#         audio = librosa.util.fix_length(audio, size=16000)

#     logging.info(f"Transcribing audio (original language): {audio_path}")

#     result = WHISPER_MODEL.transcribe(
#         audio,
#         task="transcribe",     # keep original language
#         language=None,         # auto-detect
#         fp16=False,
#         temperature=0,
#         condition_on_previous_text=False
#     )

#     raw_text = result.get("text", "").strip()
#     text = transliterate_hindi_only(raw_text)

#     logging.info("Transcription complete")
#     return text


# # ------------------------------------------------------------------
# # Speaker-wise transcription
# # ------------------------------------------------------------------

# def speaker_wise_transcription(
#     audio_path: str,
#     diarization_segments: List[Dict]
# ) -> List[Dict]:

#     if not os.path.exists(audio_path):
#         raise FileNotFoundError(f"Audio file not found: {audio_path}")

#     results = []

#     for seg in diarization_segments:
#         start = seg["start"]
#         end = seg["end"]
#         speaker_raw = seg["speaker"]

#         duration = end - start
#         if duration <= 0:
#             continue

#         audio, _ = librosa.load(
#             audio_path,
#             sr=16000,
#             mono=True,
#             offset=start,
#             duration=duration
#         )

#         if len(audio) < 16000:
#             audio = librosa.util.fix_length(audio, size=16000)

#         with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
#             sf.write(tmp.name, audio, 16000)
#             temp_audio_path = tmp.name

#         try:
#             text = transcribe_audio(temp_audio_path)
#         finally:
#             os.unlink(temp_audio_path)

#         results.append({
#             "speaker": map_speaker_label(speaker_raw),
#             "start": round(start, 2),
#             "end": round(end, 2),
#             "text": text,
#             "confidence": round(estimate_confidence(text), 2)
#         })

#     return results
import os
import torch
import whisper
import librosa
import logging
from typing import List, Dict

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ⚡ Best speed–quality tradeoff for Hindi + Hinglish
MODEL_NAME = "small"

logging.info(f"Loading Whisper model ({MODEL_NAME}) on {DEVICE}...")
WHISPER_MODEL = whisper.load_model(MODEL_NAME, device=DEVICE)
logging.info("Whisper model loaded")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def map_speaker_label(label: str) -> str:
    """
    Map diarization labels to roles.
    (Diarization already mapped in your pipeline, this is safety)
    """
    if label.lower() == "doctor":
        return "Doctor"
    if label.lower() == "patient":
        return "Patient"
    return label


def estimate_confidence(text: str) -> float:
    """
    Heuristic confidence score (Whisper doesn't expose true confidence).
    """
    if not text:
        return 0.0
    words = len(text.split())
    return round(min(0.95, 0.6 + words / 60), 2)

# ------------------------------------------------------------------
# Core transcription (ARRAY MODE, NO TEMP FILES)
# ------------------------------------------------------------------

def transcribe_audio_array(audio_array) -> str:
    """
    Transcribe a numpy audio array directly.
    Preserves original language/script.
    """

    result = WHISPER_MODEL.transcribe(
        audio_array,
        task="transcribe",
        language=None,                  # auto Hindi / English
        fp16=(DEVICE == "cuda"),
        temperature=0,
        condition_on_previous_text=False,
        no_speech_threshold=0.6
    )

    return result.get("text", "").strip()

# ------------------------------------------------------------------
# Speaker-wise transcription (FAST + CLEAN)
# ------------------------------------------------------------------

def speaker_wise_transcription(
    audio_path: str,
    diarization_segments: List[Dict]
) -> List[Dict]:

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load full audio ONCE
    audio_full, _ = librosa.load(audio_path, sr=16000, mono=True)

    results = []

    for seg in diarization_segments:
        start = seg["start"]
        end = seg["end"]
        speaker = map_speaker_label(seg["speaker"])

        start_i = int(start * 16000)
        end_i = int(end * 16000)

        segment_audio = audio_full[start_i:end_i]

        # Skip very small/noisy segments
        if len(segment_audio) < 16000:
            continue

        text = transcribe_audio_array(segment_audio)

        results.append({
            "speaker": speaker,
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text,
            "confidence": estimate_confidence(text)
        })

    return results