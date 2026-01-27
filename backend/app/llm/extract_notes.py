import json
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_NAME = "gemma:4b"   # change if your Ollama tag differs


def _build_prompt(speaker_transcript: list) -> str:
    """
    Build a strict medical extraction prompt for Gemma.
    """

    conversation = "\n".join(
        f"{seg['speaker']}: {seg['text']}"
        for seg in speaker_transcript
    )

    prompt = f"""
You are a medical documentation assistant.

From the following doctor–patient conversation, extract structured
clinical information and return ONLY valid JSON.

IMPORTANT RULES:
- Output JSON ONLY (no explanation, no markdown)
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


def extract_clinical_notes(speaker_transcript: list) -> dict:
    """
    Call Ollama (Gemma) and extract structured clinical notes.

    Args:
        speaker_transcript (list): speaker-wise transcript

    Returns:
        dict: structured clinical notes
    """

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
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error("Ollama execution failed")
        raise RuntimeError(e.stderr)

    raw_output = result.stdout.strip()

    # Ollama sometimes prints extra whitespace
    try:
        structured = json.loads(raw_output)
    except json.JSONDecodeError:
        logger.error("Invalid JSON returned by LLM")
        logger.error(raw_output)
        raise ValueError("LLM did not return valid JSON")

    logger.info("Clinical extraction complete")

    return structured


# ----------------------------------------------------------
# CLI TESTING
# ----------------------------------------------------------

if __name__ == "__main__":
    sample_input = [
        {"speaker": "Patient", "text": "I have chest pain since last night"},
        {"speaker": "Doctor", "text": "We will do an ECG and blood tests"}
    ]

    notes = extract_clinical_notes(sample_input)
    print(json.dumps(notes, indent=2))
