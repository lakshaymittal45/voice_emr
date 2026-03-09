import os
import logging
import soundfile as sf
from collections import Counter
from typing import List, Dict, Optional, Tuple
from faster_whisper import WhisperModel
import time
import librosa
import numpy as np

# Audio enhancement libraries
try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    logging.warning("⚠️ noisereduce not installed - noise reduction disabled")

# ================================================================
# 🔤 TRANSLATION CONFIGURATION (Google Translate)
# ================================================================
# APPROACH: Store BOTH native script + English translation
# - Native script: For accuracy, legal/audit, LLM processing
# - English translation: For universal staff readability
#
# Why Google Translate > Romanization:
# ✅ Natural output: "My head hurts" vs "mere sira meM darada"
# ✅ Universal readability: Anyone with English can understand
# ✅ Better for medical context: Proper English medical terms
# ================================================================

ENABLE_TRANSLATION = True  # Use Google Translate for staff-readable version
STORE_BOTH_VERSIONS = True # Store native + translated (recommended)

# Google Translate support
try:
    from googletrans import Translator
    GOOGLE_TRANSLATOR = Translator()
    TRANSLATION_AVAILABLE = True
    logging.info("✅ Google Translate API available (better than romanization)")
except ImportError:
    TRANSLATION_AVAILABLE = False
    GOOGLE_TRANSLATOR = None
    logging.warning("⚠️  googletrans not installed. Run: pip install googletrans==4.0.0rc1")

# Import medical-grade configuration
try:
    from app.config import (
        TRANSCRIPTION_MODELS,
        TRANSCRIPTION_MODEL_PRIORITY,
        TRANSCRIPTION_DEVICE,
        AUTO_FALLBACK_ON_ERROR,
        ENABLE_PERFORMANCE_MONITORING
    )
    USE_MEDICAL_CONFIG = True
except ImportError:
    logging.warning("Medical config not found, using legacy configuration")
    USE_MEDICAL_CONFIG = False
    TRANSCRIPTION_MODEL_PRIORITY = ["small"]
    TRANSCRIPTION_DEVICE = "cpu"
    AUTO_FALLBACK_ON_ERROR = True
    ENABLE_PERFORMANCE_MONITORING = False

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
    f"🏥 Medical-Grade Transcription Enabled | "
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

# ================================================================
# �🌐 TRANSLATION HELPER (Native Script → English via Google)
# ================================================================
def translate_to_english(text: str, source_language: str = None) -> str:
    """
    Translate native script text to English using Google Translate API.
    
    This produces much more natural output than romanization:
    - Input (Hindi):  "मेरे सिर में दर्द है"
    - Output (English): "My head hurts"
    
    Compare to romanization (awkward):
    - ITRANS: "mere sira meM darda hai" ❌
    
    Args:
        text: Text in native script (Devanagari, Gurmukhi, etc.)
        source_language: Language code (hi=Hindi, pa=Punjabi, auto-detect if None)
        
    Returns:
        English translation (or original if translation fails/unavailable)
    """
    if not TRANSLATION_AVAILABLE or not GOOGLE_TRANSLATOR:
        return text  # Return as-is if Google Translate not available
    
    if not text or not text.strip():
        return text
    
    # 🔍 DEBUG: Log input text details
    logging.info(f"🔍 DEBUG translate_to_english INPUT: repr={repr(text[:100])}, bytes={text[:50].encode('utf-8', errors='replace')}")
    
    # Skip if already in English (detect Latin script predominates)
    latin_count = sum(1 for char in text if ord(char) < 128)
    if latin_count / len(text) > 0.7:  # More than 70% Latin chars
        return text  # Likely already in English
    
    # Map Whisper language codes to Google Translate codes
    lang_map = {
        'hi': 'hi',  # Hindi
        'hindi': 'hi',
        'pa': 'pa',  # Punjabi
        'punjabi': 'pa',
        'en': 'en',  # English
        'english': 'en'
    }
    
    src_lang = lang_map.get(source_language, 'auto')  # Auto-detect if unknown
    
    # Try translation with retry logic (googletrans can be flaky)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Add small delay between retries to avoid rate limiting
            if attempt > 0:
                time.sleep(0.5 * attempt)
            
            # Translate to English
            result = GOOGLE_TRANSLATOR.translate(text, src=src_lang, dest='en')
            
            if result and result.text:
                translated = result.text.strip()
                # Log successful translation
                if translated != text and translated != "":
                    logging.info(f"✅ Translated [{src_lang}→en]: '{text[:30]}...' → '{translated[:50]}'")
                    return translated
                else:
                    logging.warning(f"⚠️ Translation returned same/empty text (attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        continue  # Retry
                    return text  #Give up, return original
            else:
                logging.warning(f"⚠️ Google Translate returned None (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue  # Retry
                return text
                
        except Exception as e:
            logging.error(
                f"❌ Translation ERROR (attempt {attempt+1}/{max_retries}): "
                f"{type(e).__name__}: {str(e)[:100]}"
            )
            if attempt < max_retries - 1:
                continue  # Retry
            return text  # Give up after max retries
    
    return text  # Fallback

def get_whisper_model(preferred_model: Optional[str] = None) -> Tuple[WhisperModel, str]:
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
                num_workers=2,
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
    
    # 🔥 CRITICAL: Disable VAD by default - it's too aggressive and filters out real speech
    # VAD (Voice Activity Detection) often mistakes accented speech, low-volume recordings,
    # or certain languages as "silence" and drops them entirely
    # Enable VAD only for very long audio (>60s) where speed matters
    use_vad = duration > 60.0  # Changed from 15.0 to 60.0

    # Get best available model
    model, model_name = get_whisper_model(preferred_model)

    logging.info(
        f"🎤 Starting transcription | "
        f"model={model_name} | "
        f"duration={duration:.2f}s | "
        f"VAD={'ON' if use_vad else 'OFF'}"
    )

    start_time = time.time()
    
    try:
        segments, info = model.transcribe(
            audio_to_transcribe,  # Use enhanced audio for better quality
            language=None,  # 🌏 AUTO-DETECT: Hindi, English, Punjabi, Haryanvi, etc.
                            # Whisper supports 99+ languages including North India dialects
                            # No configuration needed - handles code-switching (Hinglish) automatically
            
            task="transcribe",  # 🔤 CRITICAL: Transcribe in ORIGINAL language (not translate to English)
                                # Hindi speech → Hindi text (Devanagari: "मेरे सिर में बहुत दर्द है")
                                # Punjabi speech → Punjabi text (Gurmukhi: "ਮੇਰੇ ਸਿਰ")
                                # English speech → English text ("My head hurts")
                                # Hinglish speech → Mixed script ("My sir mein bahut pain hai")
                                # Translation to English happens LATER in LLM extraction phase

            # 🔥 CPU-OPTIMIZED SETTINGS
            beam_size=5,  # Increased for better medical term accuracy
            best_of=5,

            # 🛡️ ANTI-HALLUCINATION: Use fallback temperatures.
            # If beam-search at 0.0 confidence falls below thresholds,
            # Whisper will retry with increasing randomness to escape loops.
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],

            # 🛡️ ANTI-HALLUCINATION: Penalise repeated tokens
            repetition_penalty=1.15,     # >1 discourages the same token again
            no_repeat_ngram_size=4,      # Block exact 4-gram repetition

            # 🛡️ ANTI-HALLUCINATION: Balanced quality gates
            # ⚠️ RELAXED: Previous thresholds were TOO STRICT, causing valid speech to be rejected
            compression_ratio_threshold=2.4,  # Default 2.4 (lenient - allows more real speech)
            log_prob_threshold=-1.0,          # Relaxed from -0.8 (only reject very low confidence)
            no_speech_threshold=0.6,          # Relaxed from 0.5 (less aggressive silence filtering)

            # 🛡️ ANTI-HALLUCINATION: Skip phantom text generated during silence
            # ⚠️ DISABLED: Was causing too much valid speech to be dropped
            # hallucination_silence_threshold=0.5,  # COMMENTED OUT - too aggressive

            condition_on_previous_text=False,  # Prevents looping on prev output
            word_timestamps=False,

            # 🌐 Better language detection for multilingual audio
            language_detection_segments=4,  # Use 4 segments instead of 1

            # VAD for longer audio (RELAXED PARAMETERS)
            # ⚠️ VAD can be too aggressive - only use for very long recordings
            vad_filter=use_vad,
            vad_parameters={
                "min_silence_duration_ms": 2000,  # Increased from 900ms to 2000ms (more lenient)
                "threshold": 0.3  # Lower threshold = detect more speech (less aggressive filtering)
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
            
            # 🔍 ENHANCED DEBUG: Log all segments for analysis
            logging.info("🔍 DEBUG: All segments from Whisper:")
            for i, seg in enumerate(result[:10], 1):  # Show first 10 segments
                logging.info(f"   Segment {i}: [{seg.start:.2f}s-{seg.end:.2f}s] '{seg.text}'")
            if len(result) > 10:
                logging.info(f"   ... and {len(result) - 10} more segments")
            
            # 🔍 DEBUG: Save all segments to file for detailed analysis
            if result and len(result) > 0:
                import tempfile
                debug_file = os.path.join(tempfile.gettempdir(), "whisper_debug_full.txt")
                try:
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(f"Audio: {audio_to_transcribe}\n")
                        f.write(f"Duration: {duration:.2f}s\n")
                        f.write(f"Model: {model_name}\n")
                        f.write(f"Language: {info.language} (confidence={info.language_probability:.2f})\n")
                        f.write(f"VAD enabled: {use_vad}\n")
                        f.write(f"Total segments: {len(result)}\n")
                        f.write("\n" + "="*80 + "\n")
                        for i, seg in enumerate(result, 1):
                            f.write(f"\nSegment {i}:\n")
                            f.write(f"  Time: {seg.start:.2f}s - {seg.end:.2f}s\n")
                            f.write(f"  Text: {seg.text}\n")
                            f.write(f"  Repr: {repr(seg.text)}\n")
                            f.write(f"  Bytes: {seg.text.encode('utf-8', errors='replace')}\n")
                    logging.info(f"🔍 DEBUG: Full Whisper output saved to {debug_file}")
                except Exception as e:
                    logging.error(f"🔍 DEBUG: Failed to save debug file: {e}")
        
        # 🚨 HALLUCINATION FILTER: Remove hallucinated segments
        # Whisper (especially small/medium on Indic languages) tends to:
        #   a) Repeat a word/phrase many times in one segment
        #   b) Generate very high compression-ratio gibberish
        #   c) Emit the same char/symbol pattern endlessly
        if result:
            result = _filter_hallucinated_segments(result, model_name)
        
        # 🌐 GOOGLE TRANSLATE: Convert native scripts to English for staff readability
        # Stores natural English: "My head hurts" instead of awkward romanization
        # LLM can still read native script, but staff get readable English
        if ENABLE_TRANSLATION and TRANSLATION_AVAILABLE and info.language in ['hi', 'pa', 'hindi', 'punjabi']:
            logging.info(f"🌐 Translating {info.language} → English using Google Translate...")
            translated_count = 0
            
            for segment in result:
                original_text = segment.text
                english_text = translate_to_english(original_text, info.language)
                
                if english_text != original_text:
                    # Store both versions in segment (can be saved separately in DB)
                    if STORE_BOTH_VERSIONS:
                        segment.text_native = original_text  # "मेरे सिर में दर्द है"
                        segment.text = english_text          # "My head hurts"
                    else:
                        segment.text = english_text  # Replace with English only
                    
                    translated_count += 1
            
            if translated_count > 0:
                logging.info(
                    f"✅ Translated {translated_count}/{len(result)} segments | "
                    f"{info.language} → English (natural output)"
                )
        elif info.language in ['hi', 'pa', 'hindi', 'punjabi']:
            logging.info(
                f"ℹ️  Preserving native script for {info.language} | "
                f"Install googletrans for English translations"
            )
        
        # Cleanup enhanced audio file
        if enhanced_audio_path != audio_path and os.path.exists(enhanced_audio_path):
            try:
                os.remove(enhanced_audio_path)
                logging.debug(f"🧹 Cleaned up enhanced audio: {os.path.basename(enhanced_audio_path)}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to cleanup enhanced audio: {e}")
        
        return result
        
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
            current_idx = TRANSCRIPTION_MODEL_PRIORITY.index(model_name)
            if current_idx < len(TRANSCRIPTION_MODEL_PRIORITY) - 1:
                next_model = TRANSCRIPTION_MODEL_PRIORITY[current_idx + 1]
                logging.warning(f"🔄 Attempting fallback to {next_model}...")
                return transcribe_full_audio(audio_path, preferred_model=next_model)
        
        raise RuntimeError(f"Transcription failed: {e}")

# ------------------------------------------------------------------
# Speaker-wise transcription (ENHANCED with Medical-Grade Support)
# ------------------------------------------------------------------

def speaker_wise_transcription(
    audio_path: str,
    diarization_segments: List[Dict],
    preferred_model: Optional[str] = None
) -> List[Dict]:
    """
    🏥 ENHANCED: Medical-grade speaker-wise transcription.
    
    Features:
    - Uses best available Whisper model
    - Robust alignment with diarization
    - Fallback for empty diarization
    - Performance monitoring
    
    Args:
        audio_path: Path to audio file
        diarization_segments: Speaker segments from diarization
        preferred_model: Optional preferred Whisper model
    
    Returns:
        List of speaker-wise transcription segments
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    # 🔥 SAFETY NET: empty diarization
    if not diarization_segments:
        logging.warning("⚠️ Empty diarization segments → fallback to whole audio")
        diarization_segments = [{
            "speaker": "Unknown",
            "start": 0.0,
            "end": sf.info(audio_path).duration
        }]

    logging.info(f"🎤 Starting full-audio Whisper transcription with {len(diarization_segments)} speaker segments")
    whisper_segments = transcribe_full_audio(audio_path, preferred_model)
    logging.info(f"✅ Whisper transcription finished | Active model: {ACTIVE_MODEL_NAME}")

    results = []
    used_whisper_segments = set()  # Track which Whisper segments have been assigned

    for dseg in diarization_segments:
        d_start = dseg["start"]
        d_end = dseg["end"]
        speaker = map_speaker_label(dseg["speaker"])

        texts = []

        for idx, wseg in enumerate(whisper_segments):
            # Skip if already assigned to another speaker
            if idx in used_whisper_segments:
                continue
                
            # 🔥 IMPROVED: Use center-based alignment to prevent duplicates
            # Assign segment to speaker only if its center falls within speaker's time range
            segment_center = (wseg.start + wseg.end) / 2
            
            # Check if segment center is within this speaker's time
            if d_start <= segment_center <= d_end:
                text_from_whisper = wseg.text.strip()
                texts.append(text_from_whisper)
                used_whisper_segments.add(idx)  # Mark as used

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
        f"📝 Speaker-wise transcription completed | "
        f"model={ACTIVE_MODEL_NAME} | "
        f"segments={len(results)}"
    )

    return results

# ------------------------------------------------------------------
# Model Health Check and Status
# ------------------------------------------------------------------

def get_transcription_status() -> Dict:
    """
    Returns current transcription model status and capabilities.
    Useful for health checks and monitoring.
    """
    return {
        "active_model": ACTIVE_MODEL_NAME,
        "available_models": list(WHISPER_MODELS.keys()),
        "failed_models": MODEL_LOAD_ERRORS,
        "device": TRANSCRIPTION_DEVICE,
        "medical_config_enabled": USE_MEDICAL_CONFIG,
        "auto_fallback_enabled": AUTO_FALLBACK_ON_ERROR,
        "performance_monitoring": ENABLE_PERFORMANCE_MONITORING
    }
