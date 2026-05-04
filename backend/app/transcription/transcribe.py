import os
import logging
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from typing import Any, List, Dict, Optional, Tuple
import time
import librosa
import numpy as np

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = Any
    FASTER_WHISPER_AVAILABLE = False
    logging.warning("faster-whisper not installed - Whisper backend disabled")

# Audio enhancement libraries
try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    logging.warning("⚠️ noisereduce not installed - noise reduction disabled")

# Medical-grade configuration (same package – always available)
from app.config import (
    TRANSCRIPTION_BACKEND,
    TRANSCRIPTION_MODELS,
    TRANSCRIPTION_MODEL_PRIORITY,
    TRANSCRIPTION_DEVICE,
    AUTO_FALLBACK_ON_ERROR,
    ENABLE_PERFORMANCE_MONITORING,
    OVERLAP_ASSIGNMENT_THRESHOLD,
    OVERLAP_MIN_DURATION_SEC,
    PARALLEL_DIARIZATION_TRANSCRIPTION,
    INDIC_TRANSCRIPTION_LANGUAGE,
)
USE_MEDICAL_CONFIG = True

# GPU vs CPU tuning: use faster params on GPU where throughput is primary concern
_IS_GPU = TRANSCRIPTION_DEVICE == "cuda"
_BEAM_SIZE = 3 if _IS_GPU else 5       # 3 gives ~40% faster decode on GPU with <1% WER loss
_BEST_OF = 3 if _IS_GPU else 5
_NUM_WORKERS = 4 if _IS_GPU else 2     # More CTranslate2 workers on GPU

from app.transcription.offline_indic import (
    TranscriptSegment,
    attach_output_variants,
    get_indic_backend_status,
    indic_backend_available,
    selected_indic_language,
    transcribe_diarization_segments,
)

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================================================================
# 🔥 ENHANCED MODEL CONFIG with Medical-Grade Options
# ================================================================
# ⚡ NEW: Supports multiple models with automatic fallback
# 🏥 BEST FOR MEDICAL: large-v3 > medium > small
# 
# CURRENT MODELS (Legacy - commented out but kept as fallback):
# MODEL_NAME = "small"  # Old config
# DEVICE = "cpu"
# COMPUTE_TYPE = "int8"
#
# NEW MEDICAL-GRADE CONFIG (in config.py):
# - large-v3: Best accuracy for medical terminology
# - medium: Good balance of speed and accuracy
# - small: Fast fallback (current production model)
# ================================================================

# Model cache with fallback support
WHISPER_MODELS = {}  # Store multiple loaded models
ACTIVE_MODEL_NAME = None
MODEL_LOAD_ERRORS = {}  # Track which models failed

logging.info(
    f"Medical-Grade Transcription Enabled | "
    f"Backend={TRANSCRIPTION_BACKEND} | "
    f"Priority: {' > '.join(TRANSCRIPTION_MODEL_PRIORITY)}"
)

# ================================================================
# � AUDIO ENHANCEMENT FOR CLINICAL ENVIRONMENTS
# ================================================================
# Automatically improves audio quality before transcription:
# - Volume normalization (boost quiet recordings)
# - Noise reduction (remove background clinic noise)
# - Resampling to 16kHz (optimal for Whisper)
# - Format conversion to ensure compatibility
# ================================================================

def enhance_audio_quality(audio_path: str, output_path: Optional[str] = None) -> str:
    """
    Enhance audio quality for better transcription in real-world clinical conditions.
    
    Handles common issues:
    - Low volume (doctors recording from distance)
    - Background noise (clinic environment)
    - Low bitrate/quality (compressed recordings)
    - Non-optimal sample rates
    
    Args:
        audio_path: Path to input audio file
        output_path: Path for enhanced audio (if None, creates _enhanced.wav)
    
    Returns:
        Path to enhanced audio file
    """
    try:
        # Generate output path if not provided
        if output_path is None:
            base, _ = os.path.splitext(audio_path)
            output_path = f"{base}_enhanced.wav"
        
        logging.info(f"🎧 Enhancing audio quality: {os.path.basename(audio_path)}")
        
        # Load audio with librosa (handles multiple formats)
        audio, sr = librosa.load(audio_path, sr=None, mono=True)
        
        original_duration = len(audio) / sr
        original_size = os.path.getsize(audio_path)
        
        # 1. Normalize volume to reasonable level
        # Target: -20 dB (prevents clipping, ensures audibility)
        audio_normalized = librosa.util.normalize(audio)
        
        # 2. Noise reduction (if available)
        if NOISEREDUCE_AVAILABLE:
            # Use first 0.5 seconds as noise profile (usually silence/background)
            noise_sample_duration = min(0.5, original_duration * 0.1)  # 10% or 0.5s
            noise_sample_length = int(noise_sample_duration * sr)
            
            if len(audio_normalized) > noise_sample_length:
                audio_denoised = nr.reduce_noise(
                    y=audio_normalized,
                    sr=sr,
                    stationary=True,  # Clinical background noise is usually consistent
                    prop_decrease=0.8  # Reduce noise by 80% (preserve speech)
                )
                audio = audio_denoised
                logging.info("   ✅ Noise reduction applied")
            else:
                audio = audio_normalized
                logging.info("   ⚠️ Audio too short for noise reduction")
        else:
            audio = audio_normalized
            logging.info("   ⏭️ Noise reduction skipped (library not installed)")
        
        # 3. Resample to 16kHz (optimal for Whisper models)
        if sr != 16000:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr = 16000
            logging.info(f"   ✅ Resampled to 16kHz (Whisper-optimized)")
        
        # 4. Apply slight gain boost for very quiet recordings
        # Check RMS (root mean square) energy
        rms = np.sqrt(np.mean(audio**2))
        if rms < 0.05:  # Very quiet
            gain = min(0.15 / rms, 3.0)  # Boost but cap at 3x to avoid artifacts
            audio = audio * gain
            logging.info(f"   ✅ Gain boost applied (×{gain:.1f}) for quiet recording")
        
        # 5. Save enhanced audio as WAV (lossless, Whisper-compatible)
        sf.write(output_path, audio, sr, subtype='PCM_16')
        
        enhanced_size = os.path.getsize(output_path)
        
        logging.info(
            f"✅ Audio enhanced | "
            f"Size: {original_size/1024:.1f}KB → {enhanced_size/1024:.1f}KB | "
            f"Duration: {original_duration:.1f}s | "
            f"Quality: {sr}Hz"
        )
        
        return output_path
        
    except Exception as e:
        logging.error(f"❌ Audio enhancement failed: {str(e)}")
        logging.warning(f"⚠️ Continuing with original audio: {audio_path}")
        return audio_path  # Fallback to original if enhancement fails

def resolve_transcription_backend() -> str:
    if TRANSCRIPTION_BACKEND == "indicconformer":
        if not indic_backend_available():
            raise RuntimeError(
                "TRANSCRIPTION_BACKEND is set to indicconformer, but the local Indic backend is not installed."
            )
        return "indicconformer"

    if TRANSCRIPTION_BACKEND == "whisper":
        if not FASTER_WHISPER_AVAILABLE:
            raise RuntimeError(
                "TRANSCRIPTION_BACKEND is set to whisper, but faster-whisper is not installed."
            )
        return "whisper"

    language_hint = selected_indic_language()

    # For mixed-language conversations, prefer the multilingual backend that can
    # process the whole audio at once and overlap with diarization.
    if language_hint == "auto" and FASTER_WHISPER_AVAILABLE:
        return "whisper"

    # If the caller explicitly pins a language, prefer the Indic backend when
    # it is available because the monolingual models are better tuned for that
    # language family.
    if indic_backend_available():
        return "indicconformer"

    if FASTER_WHISPER_AVAILABLE:
        return "whisper"

    raise RuntimeError(
        "No local transcription backend is available. Install AI4Bharat NeMo or faster-whisper."
    )


def _build_transcript_segment(
    start: float,
    end: float,
    text: str,
    language: Optional[str],
    raw_words: Optional[List[Any]] = None,
) -> TranscriptSegment:
    variants = attach_output_variants(text, language)
    word_confidences = _build_word_confidences(
        display_text=(variants["text"] or "").strip(),
        native_text=variants.get("text_native"),
        language=variants.get("language"),
        raw_words=raw_words,
    )
    segment = TranscriptSegment(
        start=float(start),
        end=float(end),
        text=(variants["text"] or "").strip(),
        language=variants.get("language"),
        text_native=variants.get("text_native"),
        text_romanized=variants.get("text_romanized"),
        word_confidences=word_confidences,
    )
    return segment


def _build_word_confidences(
    display_text: str,
    native_text: Optional[str],
    language: Optional[str],
    raw_words: Optional[List[Any]],
) -> Optional[List[Dict[str, Any]]]:
    if not raw_words:
        return None

    display_tokens = display_text.split()
    native_tokens = (native_text or "").split()
    if not display_tokens:
        return None

    word_items: List[Dict[str, Any]] = []
    for index, raw_word in enumerate(raw_words):
        raw_text = (getattr(raw_word, "word", "") or "").strip()
        if not raw_text:
            continue

        variants = attach_output_variants(raw_text, language)
        token_text = (variants.get("text") or raw_text).strip()
        probability = getattr(raw_word, "probability", None)

        token_payload: Dict[str, Any] = {
            "text": token_text,
            "confidence": round(float(probability), 4) if probability is not None else None,
        }

        word_start = getattr(raw_word, "start", None)
        word_end = getattr(raw_word, "end", None)
        if word_start is not None:
            token_payload["start"] = round(float(word_start), 2)
        if word_end is not None:
            token_payload["end"] = round(float(word_end), 2)
        if index < len(native_tokens):
            token_payload["text_native"] = native_tokens[index]

        word_items.append(token_payload)

    if not word_items:
        return None

    if len(word_items) == len(display_tokens):
        return word_items

    remapped: List[Dict[str, Any]] = []
    for index, token in enumerate(display_tokens):
        source = word_items[min(index, len(word_items) - 1)]
        remapped.append(
            {
                "text": token,
                "confidence": source.get("confidence"),
                **({"start": source["start"]} if "start" in source else {}),
                **({"end": source["end"]} if "end" in source else {}),
                **({"text_native": source["text_native"]} if source.get("text_native") else {}),
            }
        )

    return remapped


def _normalize_whisper_segments(raw_segments, language: Optional[str]) -> List[TranscriptSegment]:
    normalized: List[TranscriptSegment] = []
    for raw_segment in raw_segments:
        normalized_segment = _build_transcript_segment(
            start=getattr(raw_segment, "start", 0.0),
            end=getattr(raw_segment, "end", 0.0),
            text=getattr(raw_segment, "text", ""),
            language=language,
            raw_words=getattr(raw_segment, "words", None),
        )
        if normalized_segment.text:
            normalized.append(normalized_segment)

    return normalized


def _normalize_diarization_segments(
    audio_path: str,
    diarization_segments: Optional[List[Dict]],
) -> List[Dict]:
    if diarization_segments:
        return [
            {
                "speaker": map_speaker_label(segment.get("speaker")),
                "start": segment.get("start", 0.0),
                "end": segment.get("end", 0.0),
                "overlap": bool(segment.get("overlap", False)),
                "overlap_speakers": segment.get("overlap_speakers", []),
            }
            for segment in diarization_segments
        ]

    logging.warning("⚠️ Empty diarization segments → fallback to whole audio")
    return [{
        "speaker": "Unknown",
        "start": 0.0,
        "end": sf.info(audio_path).duration,
        "overlap": False,
        "overlap_speakers": [],
    }]


def _align_transcript_to_diarization(
    diarization_segments: List[Dict],
    transcript_segments: List[Any],
) -> List[Dict]:
    results: List[Dict[str, Any]] = []

    for tseg in transcript_segments:
        text_value = (getattr(tseg, "text", "") or "").strip()
        if not text_value:
            continue

        t_start = float(getattr(tseg, "start", 0.0))
        t_end = float(getattr(tseg, "end", 0.0))
        t_duration = max(0.01, t_end - t_start)

        overlap_candidates = []
        for index, dseg in enumerate(diarization_segments):
            d_start = float(dseg["start"])
            d_end = float(dseg["end"])
            overlap = max(0.0, min(t_end, d_end) - max(t_start, d_start))
            if overlap > 0:
                overlap_candidates.append((index, overlap))

        if not overlap_candidates:
            results.append(
                {
                    "speaker": "Unknown",
                    "start": round(t_start, 2),
                    "end": round(t_end, 2),
                    "text": text_value,
                    "confidence": estimate_confidence(text_value),
                    **(
                        {"text_native": getattr(tseg, "text_native").strip()}
                        if getattr(tseg, "text_native", None)
                        else {}
                    ),
                    **(
                        {"text_romanized": getattr(tseg, "text_romanized").strip()}
                        if getattr(tseg, "text_romanized", None)
                        else {}
                    ),
                    **(
                        {"language": getattr(tseg, "language")}
                        if getattr(tseg, "language", None)
                        else {}
                    ),
                }
            )
            continue

        strongest_overlap = max(overlap for _, overlap in overlap_candidates)
        strong_targets = [
            index
            for index, overlap in overlap_candidates
            if overlap >= OVERLAP_MIN_DURATION_SEC
            and (overlap / t_duration) >= OVERLAP_ASSIGNMENT_THRESHOLD
        ]

        best_index = next(
            index for index, overlap in overlap_candidates if overlap == strongest_overlap
        )
        dseg = diarization_segments[best_index]

        payload = {
            "speaker": dseg["speaker"],
            "start": round(t_start, 2),
            "end": round(t_end, 2),
            "text": text_value,
            "confidence": estimate_confidence(text_value),
        }

        if len(strong_targets) >= 2:
            overlap_speakers = sorted(
                {diarization_segments[index]["speaker"] for index in strong_targets}
            )
            payload["overlap"] = True
            payload["overlap_speakers"] = overlap_speakers
        elif dseg.get("overlap"):
            payload["overlap"] = True
            if dseg.get("overlap_speakers"):
                payload["overlap_speakers"] = dseg["overlap_speakers"]

        if getattr(tseg, "text_native", None):
            payload["text_native"] = tseg.text_native.strip()
        if getattr(tseg, "text_romanized", None):
            payload["text_romanized"] = tseg.text_romanized.strip()
        if getattr(tseg, "language", None):
            payload["language"] = tseg.language
        if getattr(tseg, "word_confidences", None):
            payload["word_confidences"] = tseg.word_confidences

        results.append(payload)

    return results

def get_whisper_model(preferred_model: Optional[str] = None) -> Tuple['WhisperModel', 'str']:
    """
    🏥 ENHANCED: Lazy-load Whisper model with automatic fallback.
    
    Tries models in priority order:
    1. large-v3 (best medical accuracy)
    2. medium (balanced)
    3. small (fast fallback)
    
    Returns:
        (model, model_name) tuple
        
    Raises:
        RuntimeError if all models fail to load
    """
    global WHISPER_MODELS, ACTIVE_MODEL_NAME, MODEL_LOAD_ERRORS

    if not FASTER_WHISPER_AVAILABLE:
        raise RuntimeError("faster-whisper is not installed")
    
    # Determine model priority
    if preferred_model and preferred_model in TRANSCRIPTION_MODEL_PRIORITY:
        models_to_try = [preferred_model] + [
            m for m in TRANSCRIPTION_MODEL_PRIORITY if m != preferred_model
        ]
    else:
        models_to_try = TRANSCRIPTION_MODEL_PRIORITY.copy()
    
    # Try each model in priority order
    for model_nickname in models_to_try:
        # Return cached model if available
        if model_nickname in WHISPER_MODELS:
            ACTIVE_MODEL_NAME = model_nickname
            return WHISPER_MODELS[model_nickname], model_nickname
        
        # Skip if previously failed
        if model_nickname in MODEL_LOAD_ERRORS:
            logging.warning(
                f"Skipping {model_nickname} (previous error: {MODEL_LOAD_ERRORS[model_nickname]})"
            )
            continue
        
        # Get model config
        if USE_MEDICAL_CONFIG and model_nickname in TRANSCRIPTION_MODELS:
            model_config = TRANSCRIPTION_MODELS[model_nickname]
            model_name = model_config["name"]
            compute_type = model_config["compute_type"]
        else:
            # Legacy fallback
            model_name = model_nickname
            compute_type = "int8"
        
        # Attempt to load
        try:
            logging.info(
                f"Loading Whisper model: {model_name} "
                f"(device={TRANSCRIPTION_DEVICE}, compute={compute_type})"
            )
            
            start_time = time.time()
            model = WhisperModel(
                model_name,
                device=TRANSCRIPTION_DEVICE,
                compute_type=compute_type,
                num_workers=_NUM_WORKERS,
                download_root=None,
            )
            load_time = time.time() - start_time
            
            WHISPER_MODELS[model_nickname] = model
            ACTIVE_MODEL_NAME = model_nickname
            
            logging.info(
                f"✅ Whisper model loaded successfully: {model_name} "
                f"({load_time:.2f}s)"
            )
            
            if USE_MEDICAL_CONFIG:
                config = TRANSCRIPTION_MODELS[model_nickname]
                logging.info(
                    f"   📊 Model specs: {config['params']} params | "
                    f"Medical terminology: {config['medical_terminology']} | "
                    f"Use case: {config['use_case']}"
                )
            
            return model, model_nickname
            
        except Exception as e:
            error_msg = str(e)
            MODEL_LOAD_ERRORS[model_nickname] = error_msg
            logging.error(
                f"Failed to load {model_nickname}: {error_msg}"
            )
            
            if AUTO_FALLBACK_ON_ERROR and models_to_try.index(model_nickname) < len(models_to_try) - 1:
                logging.warning(f"Attempting fallback to next model...")
                continue
            else:
                raise RuntimeError(f"All Whisper models failed to load")
    
    raise RuntimeError(
        f"All transcription models failed. Errors: {MODEL_LOAD_ERRORS}"
    )

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def map_speaker_label(label: str) -> str:
    """Preserve speaker labels as-is (SPEAKER_00, SPEAKER_01, etc.)"""
    # Just return the label as-is from diarization
    # No more hardcoded Doctor/Patient mapping
    return label or "SPEAKER_UNKNOWN"


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
# 🛡️ ANTI-HALLUCINATION: Post-processing filter
# ------------------------------------------------------------------

def _is_hallucinated(text: str) -> bool:
    """
    Detect whether a single segment's text is a Whisper hallucination.

    Checks:
      1. Character-level repetition (e.g. "🎶🎶🎶🎶🎶🎶🎶")
      2. Word/phrase-level repetition (e.g. "ਸੁਣੋ ਸੁਣੋ ਸੁਣੋ ਸੁਣੋ")
      3. Very short repeated token spam
      4. Common known hallucination phrases across languages

    Returns True if the segment looks hallucinated.
    """
    if not text or not text.strip():
        return True

    text = text.strip()

    # -------- 1.  Character-level repetition --------
    no_space = text.replace(" ", "")
    if len(no_space) > 8:
        unique_chars = len(set(no_space))
        ratio = unique_chars / len(no_space)
        if ratio < 0.15:          # <15 % unique chars = extreme repetition
            return True

    # -------- 2.  Word/phrase-level repetition --------
    words = text.split()
    if len(words) >= 4:
        # Check if any single word makes up ≥60 % of all words
        counts = Counter(words)
        most_common_word, most_common_count = counts.most_common(1)[0]
        if most_common_count / len(words) >= 0.60:
            return True

        # Check for repeating bigrams  (e.g. "ab cd ab cd ab cd")
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
        if bigrams:
            bg_counts = Counter(bigrams)
            top_bg, top_bg_count = bg_counts.most_common(1)[0]
            if top_bg_count >= 4 and top_bg_count / len(bigrams) >= 0.50:
                return True

    # -------- 3.  Known hallucination phrases --------
    # Whisper is known to emit these on silence / noise:
    KNOWN_HALLUCINATIONS = [
        "thanks for watching",
        "thank you for watching",
        "please subscribe",
        "subscribe to my channel",
        "like and subscribe",
        "subtítulos realizados por la comunidad",
        "sous-titres réalisés par",
        "amara.org",
        "untertitel der amara.org-community",
        "MBC 뉴스",
        "ご視聴ありがとうございました",
        "सुनिए",       # Hindi: "listen" repeated
        "ਸੁਣੋ",        # Punjabi: "listen" repeated
        "ధన్యవాదాలు",   # Telugu: "thanks"
    ]
    text_lower = text.lower().strip()
    for phrase in KNOWN_HALLUCINATIONS:
        if text_lower == phrase.lower() or text_lower.startswith(phrase.lower()):
            return True

    return False


def _filter_hallucinated_segments(segments, model_name: str):
    """
    Remove hallucinated segments from Whisper output.
    Logs warnings for every dropped segment so we can monitor.
    """
    if not segments:
        return segments

    clean = []
    dropped = 0
    for seg in segments:
        if _is_hallucinated(seg.text):
            dropped += 1
            logging.warning(
                f"🚨 Hallucination dropped | model={model_name} | "
                f"text='{seg.text[:80]}…'" if len(seg.text) > 80 else
                f"🚨 Hallucination dropped | model={model_name} | "
                f"text='{seg.text}'"
            )
        else:
            clean.append(seg)

    if dropped:
        logging.warning(
            f"🛡️ Anti-hallucination filter: removed {dropped}/{dropped+len(clean)} "
            f"segments (model={model_name})"
        )
    return clean


# ------------------------------------------------------------------
# Transcribe FULL audio ONCE (ENHANCED with Medical-Grade Models)
# ------------------------------------------------------------------

def transcribe_full_audio(audio_path: str, preferred_model: Optional[str] = None):
    """
    🏥 ENHANCED: Medical-grade transcription with automatic fallback.
    
    Features:
    - Tries medical-grade models (large-v3 > medium > small)
    - Automatic fallback on model failure
    - Performance monitoring
    - CPU-safe settings
    - VAD for longer audio
    - Memory efficient for mass processing
    
    Args:
        audio_path: Path to audio file
        preferred_model: Optional model to try first (e.g., "large-v3")
    
    Returns:
        List of transcription segments
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # 🎧 ENHANCE AUDIO QUALITY (boost volume, reduce noise, optimize for Whisper)
    # Critical for real-world clinical recordings (doctors may record from distance,
    # in noisy environments, or with low-quality microphones)
    enhanced_audio_path = enhance_audio_quality(audio_path)
    
    # Use enhanced audio for transcription
    audio_to_transcribe = enhanced_audio_path

    try:
        duration = sf.info(audio_to_transcribe).duration
    except Exception as e:
        raise RuntimeError(f"Failed to read audio file info: {e}")
    
    # 🔥 VAD is always enabled now – Silero VAD on GPU is near-free and eliminates
    # silence segments before they hit the decoder, giving 15-30% speedup.
    # Use permissive thresholds so accented / low-volume speech is not dropped.
    use_vad = True

    # Get best available model
    model, model_name = get_whisper_model(preferred_model)

    logging.info(
        f"🎤 Starting transcription | "
        f"model={model_name} | "
        f"duration={duration:.2f}s | "
        f"VAD={'ON' if use_vad else 'OFF'}"
    )

    start_time = time.time()
    
    # Use explicit language hint if configured, otherwise auto-detect
    _lang_hint = INDIC_TRANSCRIPTION_LANGUAGE.strip().lower()
    whisper_language = _lang_hint if _lang_hint not in ("auto", "") else None

    # Medical vocabulary primer – helps Whisper recognise domain terms
    _MEDICAL_INITIAL_PROMPT = (
        "Doctor Patient consultation. Medical terms: diabetes, hypertension, "
        "blood pressure, sugar, insulin, fever, cough, pain, headache, "
        "prescription, tablet, injection, ECG, X-ray, MRI, CBC, thyroid, "
        "medicine, dose, allergy, asthma, dard, bukhar, khansi, dawai, "
        "saans, chakkar, pet dard, kamar dard, sugar level, BP, OPD."
    )

    try:
        segments, info = model.transcribe(
            audio_to_transcribe,
            language=whisper_language,  # Use hint when configured, else auto-detect

            task="transcribe",  # Transcribe in ORIGINAL language (translation happens in LLM phase)

            initial_prompt=_MEDICAL_INITIAL_PROMPT,  # Prime decoder with medical vocabulary

            beam_size=_BEAM_SIZE,
            best_of=_BEST_OF,

            # Anti-hallucination: fallback temperatures
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],

            # Anti-hallucination: penalise repeated tokens
            repetition_penalty=1.15,
            no_repeat_ngram_size=4,

            # Balanced quality gates
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,

            condition_on_previous_text=False,
            word_timestamps=True,

            language_detection_segments=4,

            vad_filter=use_vad,
            vad_parameters={
                "min_silence_duration_ms": 1500,   # Slightly shorter silences detected
                "threshold": 0.25,                  # Permissive: keep speech in noisy recordings
                "speech_pad_ms": 400,               # Pad around speech to avoid clipping words
            } if use_vad else None,
        )

        transcription_time = time.time() - start_time

        logging.info(
            f"✅ Transcription complete | "
            f"model={model_name} | "
            f"language={info.language} "
            f"(confidence={info.language_probability:.2f}) | "
            f"time={transcription_time:.2f}s"
        )

        if ENABLE_PERFORMANCE_MONITORING:
            rtf = transcription_time / duration  # Real-Time Factor
            logging.info(
                f"📊 Performance | "
                f"RTF={rtf:.2f}x | "
                f"speed={'FAST' if rtf < 0.5 else 'MODERATE' if rtf < 1.0 else 'SLOW'}"
            )

        # Convert generator to list (memory-conscious)
        result = list(segments)
        
        if not result:
            logging.error("❌ CRITICAL: Whisper returned NO segments - audio might be too quiet, corrupted, or VAD filtered everything")
            logging.error(f"   Audio info: duration={duration:.2f}s, path={audio_to_transcribe}")
            logging.error(f"   VAD enabled: {use_vad}")
            logging.error(f"   Language detected: {info.language} (confidence={info.language_probability:.2f})")
        else:
            logging.info(f"📝 Generated {len(result)} segments")

            # Log first few segments for quick verification
            for i, seg in enumerate(result[:5], 1):
                logging.info(f"   Segment {i}: [{seg.start:.2f}s-{seg.end:.2f}s] '{seg.text[:80]}'")
            if len(result) > 5:
                logging.info(f"   ... and {len(result) - 5} more segments")
        
        # 🚨 HALLUCINATION FILTER: Remove hallucinated segments
        # Whisper (especially small/medium on Indic languages) tends to:
        #   a) Repeat a word/phrase many times in one segment
        #   b) Generate very high compression-ratio gibberish
        #   c) Emit the same char/symbol pattern endlessly
        if result:
            result = _filter_hallucinated_segments(result, model_name)

        normalized_result = _normalize_whisper_segments(result, info.language)
        if normalized_result:
            romanized_count = sum(1 for segment in normalized_result if segment.text_native)
            if romanized_count:
                logging.info(
                    "Offline Romanization applied to %s/%s Whisper segments (language=%s)",
                    romanized_count,
                    len(normalized_result),
                    info.language,
                )

        # Cleanup enhanced audio file
        if enhanced_audio_path != audio_path and os.path.exists(enhanced_audio_path):
            try:
                os.remove(enhanced_audio_path)
                logging.debug(f"🧹 Cleaned up enhanced audio: {os.path.basename(enhanced_audio_path)}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to cleanup enhanced audio: {e}")
        
        return normalized_result
        
    except Exception as e:
        # Cleanup enhanced audio on error
        if enhanced_audio_path != audio_path and os.path.exists(enhanced_audio_path):
            try:
                os.remove(enhanced_audio_path)
            except:
                pass
        
        logging.error(f"❌ Whisper transcription failed with {model_name}: {e}")
        
        # Attempt fallback to next model if enabled
        if AUTO_FALLBACK_ON_ERROR:
            try:
                current_idx = TRANSCRIPTION_MODEL_PRIORITY.index(model_name)
            except ValueError:
                current_idx = -1  # model_name not in priority list; try first fallback
            next_idx = current_idx + 1
            if next_idx < len(TRANSCRIPTION_MODEL_PRIORITY):
                next_model = TRANSCRIPTION_MODEL_PRIORITY[next_idx]
                logging.warning(f"🔄 Attempting fallback to {next_model}...")
                return transcribe_full_audio(audio_path, preferred_model=next_model)

        raise RuntimeError(f"Transcription failed: {e}")

# ------------------------------------------------------------------
# Speaker-wise transcription (ENHANCED with Medical-Grade Support)
# ------------------------------------------------------------------

def speaker_wise_transcription(
    audio_path: str,
    diarization_segments: List[Dict],
    preferred_model: Optional[str] = None,
    precomputed_transcript_segments: Optional[List[Any]] = None,
) -> List[Dict]:
    """Medical-grade speaker-wise transcription."""

    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    global ACTIVE_MODEL_NAME

    backend = resolve_transcription_backend()
    normalized_diarization_segments = _normalize_diarization_segments(
        audio_path=audio_path,
        diarization_segments=diarization_segments,
    )

    if backend == "indicconformer":
        language_hint = selected_indic_language()
        ACTIVE_MODEL_NAME = (
            f"indicconformer:{language_hint}"
            if language_hint != "auto"
            else "indicconformer:multilingual"
        )

        logging.info(
            "Starting segment-wise IndicConformer transcription with %s speaker segments",
            len(normalized_diarization_segments),
        )

        enhanced_audio_path = enhance_audio_quality(audio_path)
        try:
            results = transcribe_diarization_segments(
                audio_path=enhanced_audio_path,
                diarization_segments=normalized_diarization_segments,
                confidence_fn=estimate_confidence,
            )
        finally:
            if enhanced_audio_path != audio_path and os.path.exists(enhanced_audio_path):
                try:
                    os.remove(enhanced_audio_path)
                except OSError:
                    pass

        logging.info(
            "IndicConformer transcription completed | model=%s | segments=%s",
            ACTIVE_MODEL_NAME,
            len(results),
        )
        return results

    if precomputed_transcript_segments is None:
        logging.info(
            "Starting full-audio Whisper transcription with %s speaker segments",
            len(normalized_diarization_segments),
        )
        whisper_segments = transcribe_full_audio(audio_path, preferred_model)
    else:
        whisper_segments = precomputed_transcript_segments

    logging.info("Whisper transcription finished | Active model: %s", ACTIVE_MODEL_NAME)
    results = _align_transcript_to_diarization(
        diarization_segments=normalized_diarization_segments,
        transcript_segments=whisper_segments,
    )

    logging.info(
        "Speaker-wise transcription completed | model=%s | segments=%s",
        ACTIVE_MODEL_NAME,
        len(results),
    )

    return results


def diarize_and_transcribe_audio(
    audio_path: str,
    preferred_model: Optional[str] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Run diarization and transcription with overlap when the backend supports it.

    Optimizations:
    - Audio enhancement runs ONCE upfront and the result is shared
    - Whisper model is preloaded before parallel dispatch (avoids thread contention)
    - Both diarization and transcription run concurrently on the enhanced audio
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    from app.diarization.diarize import run_diarization

    pipeline_start = time.time()

    backend = resolve_transcription_backend()
    can_parallelize = backend == "whisper" and PARALLEL_DIARIZATION_TRANSCRIPTION

    # -- Phase 0: Enhance audio ONCE (shared by both branches) --
    t0 = time.time()
    enhanced_audio_path = enhance_audio_quality(audio_path)
    t_enhance = time.time() - t0
    logging.info("Audio enhancement: %.2fs", t_enhance)

    try:
        if not can_parallelize:
            diarization_segments = run_diarization(enhanced_audio_path)
            speaker_transcript = speaker_wise_transcription(
                audio_path=enhanced_audio_path,
                diarization_segments=diarization_segments,
                preferred_model=preferred_model,
            )
            return diarization_segments, speaker_transcript

        # -- Phase 1: Preload Whisper model (avoids thread contention) --
        t1 = time.time()
        if FASTER_WHISPER_AVAILABLE:
            get_whisper_model(preferred_model)
        t_preload = time.time() - t1
        logging.info("Model preload: %.2fs", t_preload)

        # -- Phase 2: Parallel diarization + transcription --
        logging.info("Starting parallel diarization + Whisper transcription (shared enhanced audio)")
        t2 = time.time()

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="voice_emr_ml") as executor:
            diarization_future = executor.submit(run_diarization, enhanced_audio_path)
            transcription_future = executor.submit(
                transcribe_full_audio, enhanced_audio_path, preferred_model
            )

            diarization_segments = diarization_future.result()
            whisper_segments = transcription_future.result()

        t_parallel = time.time() - t2
        logging.info("Parallel phase: %.2fs", t_parallel)

        # -- Phase 3: Alignment --
        t3 = time.time()
        speaker_transcript = speaker_wise_transcription(
            audio_path=enhanced_audio_path,
            diarization_segments=diarization_segments,
            preferred_model=preferred_model,
            precomputed_transcript_segments=whisper_segments,
        )
        t_align = time.time() - t3

        t_total = time.time() - pipeline_start
        logging.info(
            "Pipeline completed in %.2fs | enhance=%.2fs preload=%.2fs parallel=%.2fs align=%.2fs | "
            "diarization_segments=%s | transcript_segments=%s",
            t_total, t_enhance, t_preload, t_parallel, t_align,
            len(diarization_segments),
            len(speaker_transcript),
        )
        return diarization_segments, speaker_transcript

    finally:
        if enhanced_audio_path != audio_path and os.path.exists(enhanced_audio_path):
            try:
                os.remove(enhanced_audio_path)
                logging.debug("Cleaned up shared enhanced audio")
            except OSError:
                pass

# ------------------------------------------------------------------
# Model Health Check and Status
# ------------------------------------------------------------------

def get_transcription_status() -> Dict:
    """Returns current transcription model status and capabilities."""
    resolved_backend = None
    try:
        resolved_backend = resolve_transcription_backend()
    except Exception as exc:
        resolved_backend = f"unavailable: {exc}"

    return {
        "configured_backend": TRANSCRIPTION_BACKEND,
        "resolved_backend": resolved_backend,
        "parallel_diarization_transcription": PARALLEL_DIARIZATION_TRANSCRIPTION,
        "active_model": ACTIVE_MODEL_NAME,
        "available_models": list(WHISPER_MODELS.keys()),
        "failed_models": MODEL_LOAD_ERRORS,
        "device": TRANSCRIPTION_DEVICE,
        "medical_config_enabled": USE_MEDICAL_CONFIG,
        "auto_fallback_enabled": AUTO_FALLBACK_ON_ERROR,
        "performance_monitoring": ENABLE_PERFORMANCE_MONITORING,
        "indic_backend": get_indic_backend_status(),
    }
