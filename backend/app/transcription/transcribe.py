import os
import torch
import whisper
import librosa
import tempfile
import soundfile as sf
import logging

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_NAME = "medium"

logging.info(f"Loading Whisper model ({MODEL_NAME}) on {DEVICE}...")
WHISPER_MODEL = whisper.load_model(MODEL_NAME, device=DEVICE)
logging.info("Whisper model loaded")

# ------------------------------------------------------------------
# Basic Transcription (FULL AUDIO)
# ------------------------------------------------------------------

# def transcribe_audio(
#     audio_path: str,
#     language: str = "en"
# ) -> str:
#     """
#     Transcribe an audio file using Whisper.

#     Args:
#         audio_path (str): Path to audio file
#         language (str): Language code (default: en)

#     Returns:
#         str: Transcribed text
#     """

#     if not os.path.exists(audio_path):
#         raise FileNotFoundError(f"Audio file not found: {audio_path}")

#     # Load & normalize audio
#     audio, sr = librosa.load(audio_path, sr=16000, mono=True)

#     # Ensure minimum length (1 second)
#     if len(audio) < 16000:
#         audio = librosa.util.fix_length(audio, size=16000)

#     # Save temp WAV for Whisper
#     with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
#         sf.write(tmp.name, audio, 16000)
#         temp_audio_path = tmp.name

#     logging.info(f"Transcribing audio: {audio_path}")

#     try:
#         result = WHISPER_MODEL.transcribe(
#             temp_audio_path,
#             language=language,
#             fp16=False,
#             temperature=0,
#             condition_on_previous_text=False
#         )
#         transcript = result.get("text", "").strip()
#     finally:
#         os.unlink(temp_audio_path)

#     logging.info("Transcription complete")
#     return transcript
def transcribe_audio(
    audio_path: str,
    language: str = "en"
) -> str:
    """
    Transcribe an audio file using Whisper (NO ffmpeg subprocess).
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load audio with librosa (already ffmpeg-safe)
    audio, sr = librosa.load(audio_path, sr=16000, mono=True)

    # Ensure minimum length
    if len(audio) < 16000:
        audio = librosa.util.fix_length(audio, size=16000)

    logging.info(f"Transcribing audio (array mode): {audio_path}")

    result = WHISPER_MODEL.transcribe(
        audio,                     # 🔥 PASS ARRAY, NOT FILE PATH
        language=language,
        fp16=False,
        temperature=0,
        condition_on_previous_text=False
    )

    transcript = result.get("text", "").strip()
    logging.info("Transcription complete")

    return transcript


# ------------------------------------------------------------------
# Speaker-wise Transcription (DIARIZATION + WHISPER)
# ------------------------------------------------------------------

def speaker_wise_transcription(
    audio_path: str,
    diarization_segments: list,
    language: str = "en"
) -> list:
    """
    Perform speaker-wise transcription using diarization segments.

    Returns:
    [
        {
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": 3.2,
            "text": "Hello doctor..."
        }
    ]
    """

    results = []

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if not diarization_segments:
        return results

    for seg in diarization_segments:
        speaker = seg["speaker"]
        start = seg["start"]
        end = seg["end"]

        duration = end - start
        if duration <= 0:
            continue

        # Load only the speaker segment
        audio, _ = librosa.load(
            audio_path,
            sr=16000,
            mono=True,
            offset=start,
            duration=duration
        )

        # Ensure minimum length
        if len(audio) < 16000:
            audio = librosa.util.fix_length(audio, size=16000)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio, 16000)
            temp_audio_path = tmp.name

        try:
            text = transcribe_audio(
                temp_audio_path,
                language=language
            )
        finally:
            os.unlink(temp_audio_path)

        results.append({
            "speaker": speaker,
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text
        })

    return results


# ------------------------------------------------------------------
# CLI Testing
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <audio_path>")
        sys.exit(1)

    audio_file = sys.argv[1]
    text = transcribe_audio(audio_file)

    print(json.dumps({"transcript": text}, indent=2))
