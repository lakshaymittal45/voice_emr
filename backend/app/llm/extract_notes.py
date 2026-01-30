import json
import subprocess
import logging
import re
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PRIMARY_MODEL = "gemma3:4b"
FALLBACK_MODEL = "qwen2.5:3b-instruct"

OLLAMA_TIMEOUT = 45
MAX_CHARS = 4000  # 🔥 prevent long LLM stalls

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

# ------------------------------------------------------------------
# Ollama availability check
# ------------------------------------------------------------------

def _ollama_available() -> bool:
    try:
        subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=5
        )
        return True
    except Exception:
        return False

# ------------------------------------------------------------------
# Prompt builder
# ------------------------------------------------------------------

def _build_prompt(speaker_transcript: List[Dict[str, str]]) -> str:
    conversation = "\n".join(
        f"{seg['speaker']}: {seg['text']}"
        for seg in speaker_transcript
        if seg.get("text")
    )

    conversation = conversation[:MAX_CHARS]

    return f"""
You are a medical documentation assistant.

The conversation may contain Hindi, English, or Hinglish.
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

# ------------------------------------------------------------------
# Ollama runner
# ------------------------------------------------------------------

def _run_ollama(model_name: str, prompt: str) -> str:
    logger.info(f"Calling Ollama model: {model_name}")

    result = subprocess.run(
        ["ollama", "run", model_name],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=OLLAMA_TIMEOUT
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result.stdout.strip()

# ------------------------------------------------------------------
# JSON parser
# ------------------------------------------------------------------

def _safe_parse_json(raw: str) -> Dict:
    if not raw or not raw.strip():
        return EMPTY_CLINICAL_NOTE.copy()

    raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
    match = re.search(r"\{[\s\S]*\}", raw)

    if not match:
        return EMPTY_CLINICAL_NOTE.copy()

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return EMPTY_CLINICAL_NOTE.copy()

# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def extract_clinical_notes(
    speaker_transcript: List[Dict[str, str]]
) -> Dict:

    if not speaker_transcript:
        return EMPTY_CLINICAL_NOTE.copy()

    if not _ollama_available():
        logger.error("Ollama not running → skipping LLM")
        return EMPTY_CLINICAL_NOTE.copy()

    prompt = _build_prompt(speaker_transcript)

    try:
        raw = _run_ollama(PRIMARY_MODEL, prompt)
        return _safe_parse_json(raw)

    except Exception as e:
        logger.warning(f"Primary model failed → fallback ({e})")

    try:
        raw = _run_ollama(FALLBACK_MODEL, prompt)
        return _safe_parse_json(raw)

    except Exception as e:
        logger.error(f"Fallback model failed → empty note ({e})")
        return EMPTY_CLINICAL_NOTE.copy()
