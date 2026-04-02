"""
🏥 Voice EMR Configuration
Medical-Grade Model Configuration with Fallback Support
Auto-detects hardware and adjusts models accordingly
"""
import os
import platform
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# ================================================================
# 🖥️ HARDWARE AUTO-DETECTION
# ================================================================

def detect_hardware() -> Dict:
    """
    Auto-detect system hardware capabilities.
    Returns dict with CPU, RAM, GPU info.
    """
    hardware_info = {
        "cpu_count": 0,
        "ram_gb": 0,
        "has_nvidia_gpu": False,
        "gpu_vram_gb": 0,
        "gpu_name": None,
        "platform": platform.system()
    }
    
    try:
        import psutil
        hardware_info["cpu_count"] = psutil.cpu_count(logical=True)
        hardware_info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
    except ImportError:
        logger.warning("psutil not installed - cannot detect CPU/RAM")
    
    # Try to detect NVIDIA GPU
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            hardware_info["has_nvidia_gpu"] = True
            hardware_info["gpu_vram_gb"] = round(gpus[0].memoryTotal / 1024, 2)
            hardware_info["gpu_name"] = gpus[0].name
    except (ImportError, Exception) as e:
        # GPU detection failed - assume CPU only
        logger.debug(f"GPU detection failed: {e}")
    
    # Fallback: Try torch CUDA detection
    if not hardware_info["has_nvidia_gpu"]:
        try:
            import torch
            if torch.cuda.is_available():
                hardware_info["has_nvidia_gpu"] = True
                hardware_info["gpu_vram_gb"] = round(
                    torch.cuda.get_device_properties(0).total_memory / (1024**3), 2
                )
                hardware_info["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception:
            pass
    
    return hardware_info

def categorize_hardware(hardware: Dict) -> str:
    """
    Categorize system into performance tier.
    Returns: 'high_end', 'mid_range', 'low_end'
    """
    ram_gb = hardware["ram_gb"]
    has_gpu = hardware["has_nvidia_gpu"]
    gpu_vram = hardware["gpu_vram_gb"]
    
    # High-end: 64+ GB RAM with powerful GPU
    if ram_gb >= 48 and has_gpu and gpu_vram >= 16:
        return "high_end"
    
    # Mid-range: 32+ GB RAM OR good GPU
    elif ram_gb >= 24 or (has_gpu and gpu_vram >= 8):
        return "mid_range"
    
    # Low-end: Everything else
    else:
        return "low_end"

def get_optimal_device() -> str:
    """
    Determine optimal device (cpu/cuda) based on hardware.
    Respects WHISPER_DEVICE env var if set.
    """
    # Check env var first
    env_device = os.getenv("WHISPER_DEVICE", "").lower()
    if env_device in ["cpu", "cuda"]:
        return env_device
    
    # Auto-detect
    hardware = detect_hardware()
    if hardware["has_nvidia_gpu"] and hardware["gpu_vram_gb"] >= 6:
        return "cuda"
    return "cpu"

def get_optimal_transcription_priority(hardware: Dict, tier: str) -> List[str]:
    """
    Get optimal transcription model priority based on hardware tier.
    """
    ram_gb = hardware["ram_gb"]
    
    if tier == "high_end":
        # Use best models
        return ["large-v3", "medium", "small"]
    elif tier == "mid_range":
        # Start with medium, fallback to small
        return ["medium", "small"]
    else:
        # Low-end: Check if we have enough RAM for medium (5GB needed)
        # Medium is MUCH better for Punjabi/Hindi than small
        if ram_gb >= 8:
            return ["medium", "small"]  # 🔥 Upgrade: medium for better quality
        else:
            return ["small"]  # Very limited systems

def get_optimal_llm_priority(hardware: Dict, tier: str) -> List[str]:
    """
    Get optimal LLM model priority based on hardware tier.
    """
    ram_gb = hardware["ram_gb"]
    
    if tier == "high_end" and ram_gb >= 64:
        # Can handle large models
        return [
            "llama3.1:70b",
            "mixtral:8x7b",
            "llama3.1:8b",
            "meditron:7b",
            "gemma3:4b",
            "qwen2.5:3b-instruct"
        ]
    elif tier == "mid_range" and ram_gb >= 24:
        # Mid-range models
        return [
            "mixtral:8x7b",
            "llama3.1:8b",
            "meditron:7b",
            "gemma3:4b",
            "qwen2.5:3b-instruct"
        ]
    else:
        # Low-end: stick with current small models
        return [
            "gemma3:4b",        # Current production
            "qwen2.5:3b-instruct" # Current fallback
        ]

# Detect hardware on module load
HARDWARE_INFO = detect_hardware()
HARDWARE_TIER = categorize_hardware(HARDWARE_INFO)
OPTIMAL_DEVICE = get_optimal_device()

# ================================================================
# 🎤 TRANSCRIPTION MODELS (Whisper)
# ================================================================
# Ranked by accuracy (best to fallback)
TRANSCRIPTION_MODELS = {
    "large-v3": {
        "name": "large-v3",
        "params": "1550M",
        "accuracy": "highest",
        "speed": "slow",
        "medical_terminology": "excellent",
        "use_case": "Production - Best accuracy for medical terms",
        "compute_type": "float16",  # Better quality
        "vram_gb": 10,
        "ram_gb": 10
    },
    "medium": {
        "name": "medium",
        "params": "769M",
        "accuracy": "high",
        "speed": "moderate",
        "medical_terminology": "good",
        "use_case": "Balanced - Good accuracy, faster",
        "compute_type": "int8",
        "vram_gb": 5,
        "ram_gb": 5
    },
    "small": {
        "name": "small",
        "params": "244M",
        "accuracy": "moderate",
        "speed": "fast",
        "medical_terminology": "fair",
        "use_case": "Current - Speed prioritized, works on any system",
        "compute_type": "int8",
        "vram_gb": 2,
        "ram_gb": 2
    }
}

# 🤖 AUTO-ADJUSTED based on detected hardware
TRANSCRIPTION_MODEL_PRIORITY = get_optimal_transcription_priority(HARDWARE_INFO, HARDWARE_TIER)
TRANSCRIPTION_DEVICE = OPTIMAL_DEVICE

# Offline transcription backend selection:
# - auto: prefer IndicConformer when configured, otherwise fallback to Whisper
# - indicconformer: use AI4Bharat IndicConformer locally
# - whisper: use faster-whisper locally
TRANSCRIPTION_BACKEND = os.getenv("TRANSCRIPTION_BACKEND", "auto").strip().lower()
if TRANSCRIPTION_BACKEND not in {"auto", "indicconformer", "whisper"}:
    logger.warning(
        "Invalid TRANSCRIPTION_BACKEND=%s, falling back to 'auto'",
        TRANSCRIPTION_BACKEND,
    )
    TRANSCRIPTION_BACKEND = "auto"

# How transcript text should be stored/displayed:
# - native: native script only
# - romanized: English letters for Indic scripts
# - both: romanized primary text plus native script metadata
TRANSCRIPT_OUTPUT_MODE = os.getenv("TRANSCRIPT_OUTPUT_MODE", "romanized").strip().lower()
if TRANSCRIPT_OUTPUT_MODE not in {"native", "romanized", "both"}:
    logger.warning(
        "Invalid TRANSCRIPT_OUTPUT_MODE=%s, falling back to 'romanized'",
        TRANSCRIPT_OUTPUT_MODE,
    )
    TRANSCRIPT_OUTPUT_MODE = "romanized"

# Optional language hint for local Indic ASR.
# Use ISO-like short codes such as hi, pa, mr, bn, ta, te, kn, ml, gu, or auto.
INDIC_TRANSCRIPTION_LANGUAGE = os.getenv("INDIC_TRANSCRIPTION_LANGUAGE", "auto").strip().lower()

# AI4Bharat model IDs. Keep multilingual as the safe default when language is unknown.
INDIC_MULTILINGUAL_MODEL = os.getenv(
    "INDIC_MULTILINGUAL_MODEL",
    "ai4bharat/indic-conformer-600m-multilingual",
).strip()
INDIC_LANGUAGE_MODELS = {
    "as": os.getenv("INDIC_MODEL_AS", "ai4bharat/indicconformer_stt_as_hybrid_ctc_rnnt_large").strip(),
    "bn": os.getenv("INDIC_MODEL_BN", "ai4bharat/indicconformer_stt_bn_hybrid_ctc_rnnt_large").strip(),
    "brx": os.getenv("INDIC_MODEL_BRX", "ai4bharat/indicconformer_stt_brx_hybrid_ctc_rnnt_large").strip(),
    "doi": os.getenv("INDIC_MODEL_DOI", "ai4bharat/indicconformer_stt_doi_hybrid_ctc_rnnt_large").strip(),
    "gu": os.getenv("INDIC_MODEL_GU", "ai4bharat/indicconformer_stt_gu_hybrid_ctc_rnnt_large").strip(),
    "hi": os.getenv("INDIC_MODEL_HI", "ai4bharat/indicconformer_stt_hi_hybrid_ctc_rnnt_large").strip(),
    "kn": os.getenv("INDIC_MODEL_KN", "ai4bharat/indicconformer_stt_kn_hybrid_ctc_rnnt_large").strip(),
    "kok": os.getenv("INDIC_MODEL_KOK", "ai4bharat/indicconformer_stt_kok_hybrid_ctc_rnnt_large").strip(),
    "ks": os.getenv("INDIC_MODEL_KS", "ai4bharat/indicconformer_stt_ks_hybrid_ctc_rnnt_large").strip(),
    "mai": os.getenv("INDIC_MODEL_MAI", "ai4bharat/indicconformer_stt_mai_hybrid_ctc_rnnt_large").strip(),
    "ml": os.getenv("INDIC_MODEL_ML", "ai4bharat/indicconformer_stt_ml_hybrid_ctc_rnnt_large").strip(),
    "mr": os.getenv("INDIC_MODEL_MR", "ai4bharat/indicconformer_stt_mr_hybrid_ctc_rnnt_large").strip(),
    "mni": os.getenv("INDIC_MODEL_MNI", "ai4bharat/indicconformer_stt_mni_hybrid_ctc_rnnt_large").strip(),
    "ne": os.getenv("INDIC_MODEL_NE", "ai4bharat/indicconformer_stt_ne_hybrid_ctc_rnnt_large").strip(),
    "or": os.getenv("INDIC_MODEL_OR", "ai4bharat/indicconformer_stt_or_hybrid_ctc_rnnt_large").strip(),
    "pa": os.getenv("INDIC_MODEL_PA", "ai4bharat/indicconformer_stt_pa_hybrid_ctc_rnnt_large").strip(),
    "sa": os.getenv("INDIC_MODEL_SA", "ai4bharat/indicconformer_stt_sa_hybrid_ctc_rnnt_large").strip(),
    "sat": os.getenv("INDIC_MODEL_SAT", "ai4bharat/indicconformer_stt_sat_hybrid_ctc_rnnt_large").strip(),
    "sd": os.getenv("INDIC_MODEL_SD", "ai4bharat/indicconformer_stt_sd_hybrid_ctc_rnnt_large").strip(),
    "ta": os.getenv("INDIC_MODEL_TA", "ai4bharat/indicconformer_stt_ta_hybrid_ctc_rnnt_large").strip(),
    "te": os.getenv("INDIC_MODEL_TE", "ai4bharat/indicconformer_stt_te_hybrid_ctc_rnnt_large").strip(),
    "ur": os.getenv("INDIC_MODEL_UR", "ai4bharat/indicconformer_stt_ur_hybrid_ctc_rnnt_large").strip(),
}

INDIC_ROMANIZABLE_LANGS = {
    "as", "bn", "brx", "gu", "hi", "kn", "kok", "ks", "mai", "ml", "mr",
    "mni", "ne", "or", "pa", "sa", "sd", "ta", "te", "ur"
}

# ================================================================
# 🧠 MEDICAL LLM MODELS (Ollama)
# ================================================================
# Ranked by medical performance (best to fallback)
MEDICAL_LLM_MODELS = {
    "llama3.1:70b": {
        "name": "llama3.1:70b",
        "params": "70B",
        "medical_performance": "excellent",
        "reasoning": "excellent",
        "speed": "slow",
        "use_case": "Production - Best medical reasoning",
        "context_window": 128000,
        "recommended": True,
        "ram_gb": 64
    },
    "meditron:70b": {
        "name": "meditron:70b",
        "params": "70B",
        "medical_performance": "excellent",
        "reasoning": "excellent",
        "speed": "slow",
        "use_case": "Medical Specialist - Trained on PubMed",
        "context_window": 8192,
        "recommended": True,
        "ram_gb": 64
    },
    "mixtral:8x7b": {
        "name": "mixtral:8x7b",
        "params": "47B",
        "medical_performance": "very good",
        "reasoning": "very good",
        "speed": "moderate",
        "use_case": "Balanced - Fast and capable",
        "context_window": 32768,
        "recommended": True,
        "ram_gb": 32
    },
    "llama3.1:8b": {
        "name": "llama3.1:8b",
        "params": "8B",
        "medical_performance": "good",
        "reasoning": "good",
        "speed": "fast",
        "use_case": "Fast processing, good quality",
        "context_window": 128000,
        "recommended": False,
        "ram_gb": 16
    },
    "biomedical-llama": {
        "name": "meditron:7b",  # Medical fine-tune
        "params": "7B",
        "medical_performance": "good",
        "reasoning": "moderate",
        "speed": "fast",
        "use_case": "Medical terminology specialist",
        "context_window": 8192,
        "recommended": False,
        "ram_gb": 16
    },
    "gemma3:4b": {
        "name": "gemma3:4b",
        "params": "4B",
        "medical_performance": "moderate",
        "reasoning": "moderate",
        "speed": "very fast",
        "use_case": "Current production - Works on any system",
        "context_window": 8192,
        "recommended": False,
        "ram_gb": 8
    },
    "qwen2.5:3b-instruct": {
        "name": "qwen2.5:3b-instruct",
        "params": "3B",
        "medical_performance": "fair",
        "reasoning": "fair",
        "speed": "very fast",
        "use_case": "Current fallback - Emergency backup",
        "context_window": 32768,
        "recommended": False,
        "ram_gb": 6
    }
}

# 🤖 AUTO-ADJUSTED based on detected hardware
# Will use current models (gemma3:4b, qwen2.5:3b) on low-end systems
# Will automatically upgrade when moved to high-end hardware
MEDICAL_LLM_PRIORITY = get_optimal_llm_priority(HARDWARE_INFO, HARDWARE_TIER)

# LLM Performance Settings
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "90"))  # Increased for larger models
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_DELAY_BASE = int(os.getenv("LLM_RETRY_DELAY_BASE", "2"))
LLM_MIN_CALL_INTERVAL = float(os.getenv("LLM_MIN_CALL_INTERVAL", "0.5"))
LLM_MAX_CHARS = int(os.getenv("LLM_MAX_CHARS", "6000"))  # Increased for better context

# ================================================================
# 🎙️ DIARIZATION (PyAnnote)
# ================================================================
DIARIZATION_CONFIG = {
    "model": "pyannote/speaker-diarization-3.1",
    "embedding_model": "pyannote/wespeaker-voxceleb-resnet34-LM",  # Better embeddings
    "min_speakers": 1,
    "max_speakers": 6,  # Doctor, Patient, (optional) Nurse
    "use_auth_token": True,
    "enhanced_preprocessing": True  # Apply noise reduction
}

# ================================================================
# 📊 MONITORING & OPTIMIZATION
# ================================================================
ENABLE_PERFORMANCE_MONITORING = True
LOG_MODEL_PERFORMANCE = True
TRACK_MEDICAL_TERMS = True  # Track medical terminology recognition

# Model warm-up on startup (prevents first-request delay)
WARMUP_MODELS_ON_STARTUP = os.getenv("WARMUP_MODELS", "false").lower() == "true"

# Cache settings
ENABLE_MODEL_CACHING = True
CACHE_TRANSCRIPTIONS = False  # Don't cache for privacy
CACHE_DIR = os.getenv("CACHE_DIR", "./model_cache")

# ================================================================
# 🔧 ROBUSTNESS SETTINGS
# ================================================================
# Automatic model fallback on errors
AUTO_FALLBACK_ON_ERROR = True

# Run full-audio Whisper transcription and diarization at the same time.
# This only applies when the resolved backend is Whisper.
PARALLEL_DIARIZATION_TRANSCRIPTION = (
    os.getenv("PARALLEL_DIARIZATION_TRANSCRIPTION", "true").strip().lower() == "true"
)

# Live transcript stabilization:
# keep a short trailing tail unsent so we do not cut speakers mid-utterance.
LIVE_TRANSCRIPT_HOLDBACK_SEC = float(
    os.getenv("LIVE_TRANSCRIPT_HOLDBACK_SEC", "1.2")
)

# Diarization post-processing:
# merge same-speaker fragments separated by tiny pauses.
DIARIZATION_MERGE_GAP_SEC = float(
    os.getenv("DIARIZATION_MERGE_GAP_SEC", "0.35")
)

# Overlap-aware speaker/text alignment:
# if a transcription segment overlaps multiple speaker turns strongly enough,
# duplicate it to both speakers instead of dropping one.
OVERLAP_ASSIGNMENT_THRESHOLD = float(
    os.getenv("OVERLAP_ASSIGNMENT_THRESHOLD", "0.45")
)
OVERLAP_MIN_DURATION_SEC = float(
    os.getenv("OVERLAP_MIN_DURATION_SEC", "0.30")
)

# Model health check intervals (seconds)
MODEL_HEALTH_CHECK_INTERVAL = 300  # 5 minutes

# Graceful degradation
ALLOW_PARTIAL_RESULTS = True  # Return partial results if LLM fails

# ================================================================
# 📝 MEDICAL PROMPT TEMPLATES
# ================================================================
MEDICAL_PROMPT_TEMPLATE = """
You are an expert medical scribe trained in SOAP-style clinical documentation.

The conversation is between a doctor and patient and may contain Hindi, English,
Hinglish, Punjabi, or Haryanvi. Internally translate everything to English before extracting.

FIELD DEFINITIONS:
- chief_complaint: Patient's main symptom or concern in their own words, with duration if mentioned.
- history_of_present_illness: Narrative of onset, location, duration, character, severity, radiation, and aggravating or relieving factors.
- associated_diseases: Active comorbidities discussed in the consultation, such as diabetes or hypertension. Do not include old resolved illnesses here.
- past_medical_history: Prior diagnoses, surgeries, hospitalizations, or significant past illnesses.
- drug_history: Current medications, including dose or frequency when explicitly stated.
- allergies: Drug or food allergies, including reaction if mentioned.
- assessment: Doctor's diagnosis, impression, or differential stated in the conversation.
- treatment_plan: Medicines prescribed, tests ordered, referrals, advice, and follow-up instructions.

STRICT RULES:
1. Extract only what is explicitly stated or clearly implied by the conversation. Do not hallucinate.
2. Negations are not findings. Examples: "no fever", "denies cough", "sugar nahi hai" should not populate positive findings.
3. If a field has no supporting information, return null.
4. If multiple items belong in one field, join them with " | ".
5. Output one valid JSON object only. No markdown, no explanation, no extra keys.
6. If the conversation is non-clinical, greeting-only, testing, or noise, return all fields as null.

OUTPUT FORMAT:
{{
  "chief_complaint": null,
  "history_of_present_illness": null,
  "associated_diseases": null,
  "past_medical_history": null,
  "drug_history": null,
  "allergies": null,
  "assessment": null,
  "treatment_plan": null
}}

CONVERSATION:
{conversation}

JSON OUTPUT:
"""

# Enhanced medical terminology extraction
MEDICAL_TERM_CATEGORIES = [
    "symptoms", "diagnoses", "medications", "procedures",
    "lab_tests", "vital_signs", "allergies", "family_history"
]

def get_active_config() -> Dict:
    """Returns current active configuration."""
    return {
        "transcription": {
            "backend": TRANSCRIPTION_BACKEND,
            "output_mode": TRANSCRIPT_OUTPUT_MODE,
            "indic_language_hint": INDIC_TRANSCRIPTION_LANGUAGE,
            "primary_model": TRANSCRIPTION_MODEL_PRIORITY[0],
            "device": TRANSCRIPTION_DEVICE,
            "fallback_models": TRANSCRIPTION_MODEL_PRIORITY[1:],
            "indic_multilingual_model": INDIC_MULTILINGUAL_MODEL,
        },
        "medical_llm": {
            "primary_model": MEDICAL_LLM_PRIORITY[0],
            "fallback_models": MEDICAL_LLM_PRIORITY[1:],
            "timeout": LLM_TIMEOUT,
            "max_retries": LLM_MAX_RETRIES
        },
        "diarization": DIARIZATION_CONFIG,
        "monitoring": {
            "enabled": ENABLE_PERFORMANCE_MONITORING,
            "log_performance": LOG_MODEL_PERFORMANCE,
            "track_medical_terms": TRACK_MEDICAL_TERMS
        },
        "robustness": {
            "auto_fallback": AUTO_FALLBACK_ON_ERROR,
            "parallel_diarization_transcription": PARALLEL_DIARIZATION_TRANSCRIPTION,
            "live_transcript_holdback_sec": LIVE_TRANSCRIPT_HOLDBACK_SEC,
            "diarization_merge_gap_sec": DIARIZATION_MERGE_GAP_SEC,
            "overlap_assignment_threshold": OVERLAP_ASSIGNMENT_THRESHOLD,
            "overlap_min_duration_sec": OVERLAP_MIN_DURATION_SEC,
            "health_check_interval": MODEL_HEALTH_CHECK_INTERVAL,
            "allow_partial_results": ALLOW_PARTIAL_RESULTS
        }
    }

def print_config_summary():
    """Print configuration summary for logging."""
    config = get_active_config()
    print("=" * 60)
    print("🏥 VOICE EMR - Medical-Grade Configuration")
    print("=" * 60)
    
    # Show hardware detection
    print(f"\n🖥️  Hardware Detection:")
    print(f"   Tier: {HARDWARE_TIER.upper()}")
    print(f"   CPU: {HARDWARE_INFO['cpu_count']} cores")
    print(f"   RAM: {HARDWARE_INFO['ram_gb']} GB")
    if HARDWARE_INFO['has_nvidia_gpu']:
        print(f"   GPU: {HARDWARE_INFO['gpu_name']} ({HARDWARE_INFO['gpu_vram_gb']} GB VRAM)")
    else:
        print(f"   GPU: None (CPU-only mode)")
    
    print(f"\n🎤 Transcription:")
    print(f"   Backend: {config['transcription']['backend']}")
    print(f"   Output: {config['transcription']['output_mode']}")
    print(f"   Indic Hint: {config['transcription']['indic_language_hint']}")
    print(f"   Primary: {config['transcription']['primary_model']}")
    print(f"   Device: {config['transcription']['device']}")
    print(f"   Fallbacks: {', '.join(config['transcription']['fallback_models']) if config['transcription']['fallback_models'] else 'None'}")
    
    print(f"\n🧠 Medical LLM:")
    print(f"   Primary: {config['medical_llm']['primary_model']}")
    print(f"   Timeout: {config['medical_llm']['timeout']}s")
    fallbacks = config['medical_llm']['fallback_models']
    if len(fallbacks) > 3:
        print(f"   Fallbacks: {', '.join(fallbacks[:3])}...")
    else:
        print(f"   Fallbacks: {', '.join(fallbacks) if fallbacks else 'None'}")
    
    print(f"\n🎙️  Diarization:")
    print(f"   Model: {config['diarization']['model']}")
    print(f"   Max Speakers: {config['diarization']['max_speakers']}")
    
    print(f"\n📊 Monitoring: {'Enabled' if config['monitoring']['enabled'] else 'Disabled'}")
    print(f"🔧 Auto Fallback: {'Enabled' if config['robustness']['auto_fallback'] else 'Disabled'}")
    print(
        f"⚡ Parallel Diarization+ASR: "
        f"{'Enabled' if config['robustness']['parallel_diarization_transcription'] else 'Disabled'}"
    )
    
    # Show optimization notes
    print(f"\n💡 Notes:")
    if HARDWARE_TIER == "low_end":
        print(f"   ⚠️  Using base models due to hardware constraints")
        print(f"   ℹ️  Install better models when you upgrade to high-end GPU")
    elif HARDWARE_TIER == "mid_range":
        print(f"   ✅ Using optimized mid-range models")
        print(f"   💡 Tip: Upgrade to 64+ GB RAM for best medical models")
    else:
        print(f"   ✅ Using best medical-grade models")
        print(f"   🏆 Your system can handle the most advanced AI")
    
    print("=" * 60)

def get_hardware_info() -> Dict:
    """Returns detected hardware information."""
    return {
        "hardware": HARDWARE_INFO,
        "tier": HARDWARE_TIER,
        "optimal_device": OPTIMAL_DEVICE,
        "transcription_priority": TRANSCRIPTION_MODEL_PRIORITY,
        "llm_priority": MEDICAL_LLM_PRIORITY
    }

if __name__ == "__main__":
    print_config_summary()
