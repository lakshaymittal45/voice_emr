import json
import subprocess
import logging
import re
import time
from typing import List, Dict, Optional, Tuple

# Import medical-grade configuration
try:
    from app.config import (
        MEDICAL_LLM_MODELS,
        MEDICAL_LLM_PRIORITY,
        LLM_TIMEOUT,
        LLM_MAX_RETRIES,
        LLM_RETRY_DELAY_BASE,
        LLM_MIN_CALL_INTERVAL,
        LLM_MAX_CHARS,
        MEDICAL_PROMPT_TEMPLATE,
        ENABLE_PERFORMANCE_MONITORING,
        AUTO_FALLBACK_ON_ERROR,
        ALLOW_PARTIAL_RESULTS
    )
    USE_MEDICAL_CONFIG = True
except ImportError:
    logging.warning("Medical config not found, using legacy configuration")
    USE_MEDICAL_CONFIG = False
    MEDICAL_LLM_PRIORITY = ["gemma3:4b", "qwen2.5:3b-instruct"]
    LLM_TIMEOUT = 45
    LLM_MAX_RETRIES = 3
    LLM_RETRY_DELAY_BASE = 2
    LLM_MIN_CALL_INTERVAL = 0.5
    LLM_MAX_CHARS = 4000
    ENABLE_PERFORMANCE_MONITORING = False
    AUTO_FALLBACK_ON_ERROR = True
    ALLOW_PARTIAL_RESULTS = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================================================
# 🏥 ENHANCED MEDICAL LLM CONFIGURATION
# ================================================================
# NEW: Medical-grade models with cascading fallback
# 
# PRIORITY ORDER (Best to Fallback):
# 1. llama3.1:70b - Excellent medical reasoning (🏆 RECOMMENDED)
# 2. mixtral:8x7b - Fast and capable alternative
# 3. llama3.1:8b - Smaller but still good
# 4. meditron:7b - Medical specialist (trained on PubMed)
# 5. gemma3:4b - Legacy fallback (CURRENT PRODUCTION)
# 6. qwen2.5:3b-instruct - Emergency fallback
#
# OLD CONFIGURATION (commented out but kept as final fallback):
# PRIMARY_MODEL = "gemma3:4b"
# FALLBACK_MODEL = "qwen2.5:3b-instruct"
# OLLAMA_TIMEOUT = 45
# MAX_CHARS = 4000
# ================================================================

# Model state tracking
ACTIVE_LLM_MODEL = None
LLM_MODEL_ERRORS = {}  # Track failed models
OLLAMA_HEALTHY = None  # Cache Ollama health status
last_llm_call_time = 0
last_health_check_time = 0
HEALTH_CHECK_INTERVAL = 300  # 5 minutes

logger.info(
    f"🏥 Medical-Grade LLM Enabled | "
    f"Priority: {' > '.join(MEDICAL_LLM_PRIORITY[:3])}..."
)

EMPTY_CLINICAL_NOTE = {
    "chief_complaint": None,
    "history_of_present_illness": None,
    "associated_diseases": None,
    "past_medical_history": None,
    "drug_history": None,
    "allergies": None,
    "assessment": None,
    "treatment_plan": None
}

NON_CLINICAL_PATTERNS = [
    r"^\s*$",
    r"^[\d\s,.\-]+$",
]

NON_CLINICAL_PHRASES = {
    "hello",
    "hi",
    "testing",
    "test",
    "one two three",
    "1 2 3",
    "123",
    "kya haal hai",
    "kaise ho",
    "haan",
    "hanji",
    "theek hai",
    "thik hai",
    "acha",
    "achha",
}

CLINICAL_CUES = {
    "pain", "fever", "cough", "cold", "sugar", "diabetes", "bp", "pressure",
    "vomit", "vomiting", "headache", "dizzy", "dizziness", "weakness", "weak",
    "breath", "breathing", "asthma", "chest", "stomach", "abdomen", "infection",
    "tablet", "medicine", "medication", "allergy", "allergies", "doctor",
    "patient", "symptom", "symptoms", "days", "months", "years", "pregnant",
    "injury", "fracture", "blood", "surgery", "insulin", "thyroid", "urine",
    "bukhar", "khansi", "sar", "sir", "dard", "saans", "dawai", "davai",
    "ulti", "chakkar", "pet", "sardi", "bukhaar", "sugar", "ghabrahat",
    "khang", "dawaiyan", "allergy", "bukhar hai", "khansi hai", "dard hai",
}

ROLE_CUES = {
    "doctor", "dr", "patient", "medicine", "prescription", "clinic", "hospital",
    "test", "report", "symptom", "problem", "complaint", "tablet", "bp",
    "sugar", "scan", "xray", "ultrasound", "follow up", "followup",
}

LYRIC_CUES = {
    "mohabbat", "mahubat", "muhabbat", "pyaar", "pyar", "ishq", "dil", "darling",
    "break up", "breakup", "sanam", "jana", "jaan", "yaar", "yaaron", "baby",
    "mili", "mujhko", "mar jaunga", "mar jaunga", "give up", "love", "lover",
}

# ------------------------------------------------------------------
# 🏥 Ollama Health Check (Enhanced)
# ------------------------------------------------------------------

def _ollama_available() -> bool:
    """
    Check if Ollama is running and healthy.
    Uses caching to reduce overhead for mass processing.
    """
    global OLLAMA_HEALTHY, last_health_check_time
    
    # Use cached result if recent
    current_time = time.time()
    if (OLLAMA_HEALTHY is not None and 
        current_time - last_health_check_time < HEALTH_CHECK_INTERVAL):
        return OLLAMA_HEALTHY
    
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=5,
            text=True
        )
        
        OLLAMA_HEALTHY = (result.returncode == 0)
        last_health_check_time = current_time
        
        if OLLAMA_HEALTHY:
            # Log available models
            models = result.stdout.strip().split('\n')
            available_models = [m.split()[0] for m in models[1:] if m.strip()]
            logger.info(f"Ollama healthy | Available models: {len(available_models)}")
        else:
            logger.warning("Ollama not responding properly")
        
        return OLLAMA_HEALTHY
        
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        OLLAMA_HEALTHY = False
        last_health_check_time = current_time
        return False

def check_model_availability(model_name: str) -> bool:
    """Check if a specific model is installed in Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=5,
            text=True
        )
        
        if result.returncode == 0:
            # Parse model list
            available = [line.split()[0] for line in result.stdout.split('\n')[1:] if line.strip()]
            is_available = model_name in available
            
            if not is_available:
                logger.debug(f"Model {model_name} not found in Ollama. Install with: ollama pull {model_name}")
            
            return is_available
        
        return False
        
    except Exception:
        return False

# ------------------------------------------------------------------
# 🏥 Enhanced Medical Prompt Builder
# ------------------------------------------------------------------

def _format_segment_for_prompt(seg: Dict[str, str]) -> Optional[str]:
    text = (seg.get("text") or "").strip()
    if not text:
        return None

    native_text = (seg.get("text_native") or "").strip()
    romanized_text = (seg.get("text_romanized") or "").strip()
    speaker = seg.get("speaker") or "Speaker"

    if native_text and native_text != text and native_text not in text:
        return f"{speaker}: {text} [native: {native_text}]"

    if romanized_text and romanized_text != text and romanized_text not in text:
        return f"{speaker}: {text} [romanized: {romanized_text}]"

    return f"{speaker}: {text}"


def _build_prompt(speaker_transcript: List[Dict[str, str]], use_enhanced: bool = True) -> str:
    """
    Build medical-grade prompt with enhanced structure.
    
    Args:
        speaker_transcript: List of speaker segments
        use_enhanced: Use enhanced medical prompt template
    
    Returns:
        Formatted prompt string
    """
    conversation_lines = []
    for segment in speaker_transcript:
        formatted = _format_segment_for_prompt(segment)
        if formatted:
            conversation_lines.append(formatted.strip())

    conversation = "\n".join(line for line in conversation_lines if line)

    # Truncate to prevent timeout
    if len(conversation) > LLM_MAX_CHARS:
        logger.warning(
            "Transcript truncated for LLM prompt: %s -> %s chars",
            len(conversation),
            LLM_MAX_CHARS,
        )
        conversation = conversation[:LLM_MAX_CHARS]

    if USE_MEDICAL_CONFIG and use_enhanced:
        # Use enhanced medical template
        return MEDICAL_PROMPT_TEMPLATE.format(conversation=conversation)
    else:
        # Legacy prompt (simpler, for smaller models)
        return f"""
You are a medical documentation assistant.

The conversation may contain Hindi, English, Hinglish, Punjabi, or Haryanvi.
Internally translate to English before extracting information.

IMPORTANT:
- If no clinical information is present, return all fields as null.
- Do NOT hallucinate.

RULES:
- Output ONE valid JSON object only
- No explanations, no markdown, no extra text
- Use null if information is missing

Return JSON with EXACT keys:
chief_complaint
history_of_present_illness
associated_diseases
past_medical_history
drug_history
allergies
assessment
treatment_plan

Conversation:
{conversation}
""".strip()


def _transcript_text_for_validation(speaker_transcript: List[Dict[str, str]]) -> str:
    parts = []
    for segment in speaker_transcript:
        for key in ("text", "text_native", "text_romanized"):
            value = (segment.get(key) or "").strip().lower()
            if value:
                parts.append(value)
    return " ".join(parts)


def _looks_non_clinical_transcript(speaker_transcript: List[Dict[str, str]]) -> bool:
    combined = _transcript_text_for_validation(speaker_transcript)
    if not combined:
        return True

    normalized = re.sub(r"[^\w\s]", " ", combined)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return True

    for pattern in NON_CLINICAL_PATTERNS:
        if re.fullmatch(pattern, normalized):
            return True

    word_count = len(normalized.split())
    if normalized in NON_CLINICAL_PHRASES:
        return True

    clinical_cue_count = sum(1 for cue in CLINICAL_CUES if cue in normalized)
    role_cue_count = sum(1 for cue in ROLE_CUES if cue in normalized)
    lyric_cue_count = sum(1 for cue in LYRIC_CUES if cue in normalized)
    speaker_count = len(
        {
            (segment.get("speaker") or "").strip()
            for segment in speaker_transcript
            if (segment.get("speaker") or "").strip()
        }
    )

    # Reject short, greeting-like, or number-heavy audio before the LLM can hallucinate.
    if word_count < 8 and clinical_cue_count == 0:
        return True

    # Reject likely songs/lyrics/monologues unless there is strong clinical evidence.
    if lyric_cue_count >= 2 and clinical_cue_count < 3:
        return True

    # A single-speaker monologue without medical context is not a consultation.
    if speaker_count <= 1 and clinical_cue_count < 3 and role_cue_count == 0:
        return True

    # Require stronger evidence before calling the LLM.
    if clinical_cue_count < 2 and role_cue_count == 0:
        return True

    return False

# ------------------------------------------------------------------
# 🏥 Enhanced Ollama Runner with Intelligent Retry
# ------------------------------------------------------------------

def _run_ollama(
    model_name: str, 
    prompt: str, 
    retry_count: int = 0,
    timeout: Optional[int] = None
) -> Tuple[str, Dict]:
    """
    Run Ollama with enhanced retry logic, rate limiting, and performance monitoring.
    
    Args:
        model_name: Name of the Ollama model to run
        prompt: Prompt to send to the model
        retry_count: Current retry attempt (internal)
        timeout: Optional timeout override
        
    Returns:
        Tuple of (response_text, metrics_dict)
        
    Raises:
        RuntimeError: If all retries fail
    """
    global last_llm_call_time, ACTIVE_LLM_MODEL
    
    # Simple rate limiting
    elapsed = time.time() - last_llm_call_time
    if elapsed < LLM_MIN_CALL_INTERVAL:
        sleep_time = LLM_MIN_CALL_INTERVAL - elapsed
        logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
        time.sleep(sleep_time)
    
    timeout_val = timeout or LLM_TIMEOUT
    
    # Log model info on first use
    if USE_MEDICAL_CONFIG and model_name in MEDICAL_LLM_MODELS and ACTIVE_LLM_MODEL != model_name:
        config = MEDICAL_LLM_MODELS[model_name]
        logger.info(
            f"🧠 Using LLM: {model_name} | "
            f"Params: {config['params']} | "
            f"Medical Performance: {config['medical_performance']} | "
            f"Use case: {config['use_case']}"
        )
        ACTIVE_LLM_MODEL = model_name
    
    logger.info(
        f"📤 Calling Ollama | "
        f"model={model_name} | "
        f"attempt={retry_count + 1}/{LLM_MAX_RETRIES + 1} | "
        f"timeout={timeout_val}s"
    )

    start_time = time.time()
    
    try:
        result = subprocess.run(
            ["ollama", "run", model_name],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_val
        )
        
        elapsed_time = time.time() - start_time
        last_llm_call_time = time.time()
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown Ollama error"
            logger.warning(f"❌ Ollama returned error (code={result.returncode}): {error_msg[:200]}")
            raise RuntimeError(f"Ollama error: {error_msg}")
        
        response = result.stdout.strip()
        
        # Performance metrics
        metrics = {
            "model": model_name,
            "elapsed_time": round(elapsed_time, 2),
            "response_length": len(response),
            "retry_count": retry_count,
            "success": True
        }
        
        if ENABLE_PERFORMANCE_MONITORING:
            logger.info(
                f"✅ LLM response received | "
                f"model={model_name} | "
                f"time={elapsed_time:.2f}s | "
                f"length={len(response)} chars"
            )
        
        return response, metrics
        
    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        error_msg = f"Ollama timeout after {elapsed_time:.1f}s (limit: {timeout_val}s)"
        logger.warning(f"⏱️ {error_msg}")
        
        # Exponential backoff retry
        if retry_count < LLM_MAX_RETRIES:
            delay = LLM_RETRY_DELAY_BASE ** (retry_count + 1)
            logger.info(f"🔄 Retrying after {delay}s...")
            time.sleep(delay)
            return _run_ollama(model_name, prompt, retry_count + 1, timeout)
        else:
            raise RuntimeError(error_msg)
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Ollama execution failed: {str(e)[:200]}"
        logger.error(f"❌ {error_msg}")
        
        # Retry for potentially transient errors
        should_retry = (
            retry_count < LLM_MAX_RETRIES and 
            any(keyword in str(e).lower() for keyword in ["connection", "network", "refused", "reset"])
        )
        
        if should_retry:
            delay = LLM_RETRY_DELAY_BASE ** (retry_count + 1)
            logger.info(f"🔄 Retrying after {delay}s due to transient error...")
            time.sleep(delay)
            return _run_ollama(model_name, prompt, retry_count + 1, timeout)
        else:
            raise RuntimeError(error_msg)

# ------------------------------------------------------------------
# 🏥 Enhanced JSON Parser
# ------------------------------------------------------------------

def _safe_parse_json(raw: str, strict: bool = False) -> Tuple[Dict, bool]:
    """
    Parse JSON response with enhanced validation.
    
    Args:
        raw: Raw LLM response
        strict: If True, require all fields to be present
        
    Returns:
        Tuple of (parsed_dict, is_valid)
    """
    if not raw or not raw.strip():
        logger.warning("Empty LLM response")
        return EMPTY_CLINICAL_NOTE.copy(), False

    # Remove markdown code blocks
    raw = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"```", "", raw).strip()
    
    # Find JSON object
    match = re.search(r"\{[\s\S]*\}", raw)

    if not match:
        logger.warning("No JSON object found in LLM response")
        return EMPTY_CLINICAL_NOTE.copy(), False

    try:
        parsed = json.loads(match.group())
        
        # Validate structure
        expected_keys = set(EMPTY_CLINICAL_NOTE.keys())
        actual_keys = set(parsed.keys())
        
        if not expected_keys.issubset(actual_keys):
            missing = expected_keys - actual_keys
            logger.warning(f"Missing fields in LLM response: {missing}")
            # Fill missing fields
            for key in missing:
                parsed[key] = None
        
        # Check if we got useful data
        has_data = any(v is not None and str(v).strip() for v in parsed.values())
        
        if not has_data and strict:
            logger.warning("LLM returned all-null clinical note")
            return parsed, False
        
        logger.debug(f"Successfully parsed clinical note (fields with data: {sum(1 for v in parsed.values() if v)})")
        return parsed, True
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return EMPTY_CLINICAL_NOTE.copy(), False

# ------------------------------------------------------------------
# 🏥 Medical-Grade Clinical Note Extraction with Cascading Fallback
# ------------------------------------------------------------------

def extract_clinical_notes(
    speaker_transcript: List[Dict[str, str]],
    preferred_model: Optional[str] = None
) -> Dict:
    """
    🏥 ENHANCED: Extract clinical notes using medical-grade LLMs with cascading fallback.
    
    Features:
    - Tries multiple medical LLMs in priority order
    - Automatic fallback on model failure
    - Enhanced medical prompts for larger models
    - Performance monitoring
    - Graceful degradation
    
    Model Priority (default):
    1. llama3.1:70b - Best medical reasoning
    2. mixtral:8x7b - Fast and capable
    3. llama3.1:8b - Smaller but good
    4. meditron:7b - Medical specialist
    5. gemma3:4b - Legacy (current production)
    6. qwen2.5:3b-instruct - Final fallback
    
    Args:
        speaker_transcript: List of speaker segments with text
        preferred_model: Optional model to try first
        
    Returns:
        Dict with clinical note fields (may be empty if all models fail)
    """

    if not speaker_transcript:
        logger.warning("Empty transcript provided to LLM")
        return EMPTY_CLINICAL_NOTE.copy()

    if _looks_non_clinical_transcript(speaker_transcript):
        logger.warning(
            "Skipping clinical note extraction because transcript does not contain enough clinical signal"
        )
        return EMPTY_CLINICAL_NOTE.copy()

    # Check Ollama health
    if not _ollama_available():
        logger.error("❌ Ollama not running or not available")
        if ALLOW_PARTIAL_RESULTS:
            logger.warning("Returning empty clinical note due to Ollama unavailability")
            return EMPTY_CLINICAL_NOTE.copy()
        else:
            raise RuntimeError("Ollama is not available")

    # Build prompt optimized for conversation length
    prompt = _build_prompt(speaker_transcript, use_enhanced=True)
    logger.info(f"📝 Built prompt | length={len(prompt)} chars | segments={len(speaker_transcript)}")

    # Determine model priority
    if preferred_model and preferred_model in MEDICAL_LLM_PRIORITY:
        models_to_try = [preferred_model] + [
            m for m in MEDICAL_LLM_PRIORITY if m != preferred_model
        ]
    else:
        models_to_try = MEDICAL_LLM_PRIORITY.copy()
    
    logger.info(f"🎯 Will try {len(models_to_try)} models: {' → '.join(models_to_try[:3])}...")
    
    all_metrics = []
    
    # Try each model in priority order
    for idx, model_name in enumerate(models_to_try):
        # Skip if previously marked as unavailable
        if model_name in LLM_MODEL_ERRORS:
            logger.debug(f"Skipping {model_name} (previously failed: {LLM_MODEL_ERRORS[model_name][:50]})")
            continue
        
        # Check if model is installed
        if not check_model_availability(model_name):
            error = f"Model not installed"
            LLM_MODEL_ERRORS[model_name] = error
            logger.warning(f"❌ {model_name}: {error}. Install with: ollama pull {model_name}")
            
            # For recommended models, show clear installation message
            if USE_MEDICAL_CONFIG and model_name in MEDICAL_LLM_MODELS:
                config = MEDICAL_LLM_MODELS[model_name]
                if config.get("recommended"):
                    logger.warning(
                        f"💡 {model_name} is RECOMMENDED for medical use. "
                        f"Install it for better performance: ollama pull {model_name}"
                    )
            continue
        
        try:
            logger.info(f"🧠 Attempting model {idx+1}/{len(models_to_try)}: {model_name}")
            
            # Use enhanced prompt for larger models, simpler for smaller ones
            use_enhanced_prompt = (
                USE_MEDICAL_CONFIG and 
                model_name in MEDICAL_LLM_MODELS and 
                MEDICAL_LLM_MODELS[model_name].get("params", "").endswith("B") and
                not model_name.endswith(":3b")
            )
            
            if not use_enhanced_prompt and idx > 0:
                # Rebuild with simpler prompt for smaller models
                prompt = _build_prompt(speaker_transcript, use_enhanced=False)
            
            # Run LLM
            raw_response, metrics = _run_ollama(model_name, prompt)
            all_metrics.append(metrics)
            
            # Parse response
            result, is_valid = _safe_parse_json(raw_response, strict=False)
            
            # Check if we got useful data
            has_data = any(v is not None and str(v).strip() for v in result.values())
            
            if is_valid and has_data:
                logger.info(
                    f"✅ Successfully extracted clinical notes | "
                    f"model={model_name} | "
                    f"fields_filled={sum(1 for v in result.values() if v)}/8"
                )
                
                if ENABLE_PERFORMANCE_MONITORING and all_metrics:
                    avg_time = sum(m['elapsed_time'] for m in all_metrics) / len(all_metrics)
                    logger.info(f"📊 Average LLM time: {avg_time:.2f}s | Attempts: {len(all_metrics)}")
                
                return result
            else:
                logger.warning(
                    f"⚠️ {model_name} returned {'invalid' if not is_valid else 'empty'} response"
                )
                
                # Try next model if this was invalid
                if AUTO_FALLBACK_ON_ERROR and idx < len(models_to_try) - 1:
                    logger.info(f"🔄 Trying next model in fallback chain...")
                    continue
                elif not AUTO_FALLBACK_ON_ERROR:
                    # Return even if empty when fallback disabled
                    return result
            
        except Exception as e:
            error_msg = str(e)[:200]
            LLM_MODEL_ERRORS[model_name] = error_msg
            logger.error(f"❌ {model_name} failed: {error_msg}")
            
            # Try next model if available
            if AUTO_FALLBACK_ON_ERROR and idx < len(models_to_try) - 1:
                logger.warning(f"🔄 Falling back to next model...")
                continue
            else:
                # Last model failed
                break
    
    # All models failed or returned empty
    logger.error(
        f"❌ All LLM extraction attempts failed or returned empty | "
        f"Tried {len(all_metrics)} models"
    )
    
    if ALLOW_PARTIAL_RESULTS:
        logger.warning("Returning empty clinical note (partial results allowed)")
        return EMPTY_CLINICAL_NOTE.copy()
    else:
        raise RuntimeError("All LLM models failed to extract clinical notes")

# ------------------------------------------------------------------
# Model Health Check and Status
# ------------------------------------------------------------------

def get_llm_status() -> Dict:
    """
    Returns current LLM model status and capabilities.
    Useful for health checks and monitoring.
    """
    return {
        "active_model": ACTIVE_LLM_MODEL,
        "failed_models": LLM_MODEL_ERRORS,
        "ollama_healthy": OLLAMA_HEALTHY,
        "medical_config_enabled": USE_MEDICAL_CONFIG,
        "auto_fallback_enabled": AUTO_FALLBACK_ON_ERROR,
        "performance_monitoring": ENABLE_PERFORMANCE_MONITORING,
        "model_priority": MEDICAL_LLM_PRIORITY,
        "timeout": LLM_TIMEOUT,
        "max_retries": LLM_MAX_RETRIES
    }
