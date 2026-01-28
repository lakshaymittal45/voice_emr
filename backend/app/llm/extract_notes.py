import json
import subprocess
import logging
import re
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_NAME = "gemma3:4b"


def _build_prompt(speaker_transcript: List[Dict[str, str]]) -> str:
    conversation = "\n".join(
        f"{seg['speaker']}: {seg['text']}"
        for seg in speaker_transcript
        if seg.get("text")
    )

    prompt = f"""
You are a medical documentation assistant.

The following doctor–patient conversation may contain Hindi, English,
or mixed Hindi-English (Hinglish).

IMPORTANT:
- First, internally translate the entire conversation into English.
- Then extract clinical information based on the translated meaning.
- DO NOT include the translated conversation in the output.
- DO NOT include explanations, reasoning, or markdown.

STRICT OUTPUT RULES:
- Output ONLY valid JSON
- Use null if information is missing
- Do not hallucinate
- Be concise and clinically accurate

Return JSON with EXACT keys:
- chief_complaint
- history_of_present_illness
- associated_diseases
- past_medical_history
- drug_history
- allergies
- assessment
- treatment_plan

Conversation:
<<<
{conversation}
>>>
"""
    return prompt.strip()


def extract_clinical_notes(
    speaker_transcript: List[Dict[str, str]]
) -> Dict:

    if not speaker_transcript:
        raise ValueError("Empty speaker transcript passed to LLM")

    prompt = _build_prompt(speaker_transcript)
    logger.info("Calling Ollama for clinical extraction...")

    try:
        result = subprocess.run(
            ["ollama", "run", MODEL_NAME],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error("Ollama execution failed")
        logger.error("STDOUT:\n%s", e.stdout)
        logger.error("STDERR:\n%s", e.stderr)
        raise RuntimeError("Ollama failed during clinical extraction")

    raw_output = result.stdout.strip()

    match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    if not match:
        logger.error("No valid JSON found in LLM output")
        logger.error("Raw output:\n%s", raw_output)
        raise ValueError("LLM did not return valid JSON")

    try:
        structured = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.error("JSON parsing failed")
        logger.error("Extracted JSON:\n%s", match.group())
        raise ValueError("Malformed JSON returned by LLM") from e

    logger.info("Clinical extraction complete")
    return structured