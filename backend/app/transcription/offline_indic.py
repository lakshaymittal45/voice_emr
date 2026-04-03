import logging
import os
import re
import tempfile
import unicodedata
import uuid
import inspect
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import soundfile as sf

from app.config import (
    INDIC_LANGUAGE_MODELS,
    INDIC_MULTILINGUAL_MODEL,
    INDIC_ROMANIZABLE_LANGS,
    INDIC_TRANSCRIPTION_LANGUAGE,
    TRANSCRIPTION_DEVICE,
    TRANSCRIPT_OUTPUT_MODE,
)

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    text_native: Optional[str] = None
    text_romanized: Optional[str] = None
    word_confidences: Optional[List[Dict[str, Any]]] = None


_INDIC_MODELS: Dict[str, Any] = {}
_IMPORT_ERRORS: Dict[str, str] = {}
_TRANSLITERATOR: Any = None
_TRANSLITERATOR_BACKEND: Optional[str] = None
_TRANSLITERATOR_WARNED = False

_LANGUAGE_ALIASES = {
    "asm": "as",
    "assamese": "as",
    "ben": "bn",
    "bengali": "bn",
    "guj": "gu",
    "gujarati": "gu",
    "hin": "hi",
    "hindi": "hi",
    "kan": "kn",
    "kannada": "kn",
    "kok": "kok",
    "konkani": "kok",
    "kas": "ks",
    "kashmiri": "ks",
    "mai": "mai",
    "maithili": "mai",
    "mal": "ml",
    "malayalam": "ml",
    "mar": "mr",
    "marathi": "mr",
    "mni": "mni",
    "manipuri": "mni",
    "nep": "ne",
    "nepali": "ne",
    "ori": "or",
    "orya": "or",
    "odia": "or",
    "pan": "pa",
    "punjabi": "pa",
    "panjabi": "pa",
    "san": "sa",
    "sanskrit": "sa",
    "sat": "sat",
    "santali": "sat",
    "snd": "sd",
    "sindhi": "sd",
    "tam": "ta",
    "tamil": "ta",
    "tel": "te",
    "telugu": "te",
    "urd": "ur",
    "urdu": "ur",
}


def normalize_language_code(language: Optional[str]) -> str:
    if not language:
        return "auto"

    normalized = language.strip().lower()
    return _LANGUAGE_ALIASES.get(normalized, normalized)


def selected_indic_language() -> str:
    return normalize_language_code(INDIC_TRANSCRIPTION_LANGUAGE)


def indic_model_id_for_language(language: Optional[str]) -> str:
    normalized = normalize_language_code(language)
    return INDIC_LANGUAGE_MODELS.get(normalized) or INDIC_MULTILINGUAL_MODEL


def _load_nemo_asr_model():
    try:
        from nemo.collections.asr.models import ASRModel

        return ASRModel
    except ImportError as exc:
        message = (
            "IndicConformer backend requires AI4Bharat NeMo locally. "
            "Install the AI4Bharat NeMo fork and try again."
        )
        _IMPORT_ERRORS["nemo"] = str(exc)
        raise RuntimeError(message) from exc


def indic_backend_available() -> bool:
    try:
        _load_nemo_asr_model()
        return True
    except RuntimeError:
        return False


def _coerce_transcription_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if hasattr(result, "text"):
        return str(result.text).strip()
    if isinstance(result, dict):
        for key in ("text", "pred_text", "transcript"):
            if result.get(key):
                return str(result[key]).strip()
    return str(result).strip()


def get_indic_asr_model(language: Optional[str]) -> Any:
    model_id = indic_model_id_for_language(language)
    if model_id in _INDIC_MODELS:
        return _INDIC_MODELS[model_id]

    ASRModel = _load_nemo_asr_model()
    logger.info(
        "Loading IndicConformer model: %s (device=%s)",
        model_id,
        TRANSCRIPTION_DEVICE,
    )

    if os.path.isfile(model_id) and model_id.endswith(".nemo"):
        model = ASRModel.restore_from(model_id)
    else:
        model = ASRModel.from_pretrained(model_name=model_id)

    try:
        if TRANSCRIPTION_DEVICE == "cuda":
            model = model.cuda()
        else:
            model = model.cpu()
    except Exception as exc:
        logger.warning("Could not move IndicConformer model to %s: %s", TRANSCRIPTION_DEVICE, exc)

    if hasattr(model, "freeze"):
        model.freeze()
    if hasattr(model, "eval"):
        model.eval()

    _INDIC_MODELS[model_id] = model
    return model


def transcribe_files_with_indicconformer(
    audio_paths: Sequence[str],
    language: Optional[str],
) -> List[str]:
    if not audio_paths:
        return []

    model = get_indic_asr_model(language)
    batch_size = min(4, len(audio_paths))

    try:
        raw_results = model.transcribe(list(audio_paths), batch_size=batch_size)
    except TypeError:
        raw_results = model.transcribe(list(audio_paths))

    if isinstance(raw_results, tuple):
        raw_results = raw_results[0]

    return [_coerce_transcription_text(item) for item in raw_results]


def _load_transliterator():
    global _TRANSLITERATOR, _TRANSLITERATOR_BACKEND, _TRANSLITERATOR_WARNED

    if _TRANSLITERATOR is not None:
        return _TRANSLITERATOR

    try:
        from ai4bharat.transliteration import XlitEngine
        signature = inspect.signature(XlitEngine)

        # Newer API variants support constructor options for Indic pipelines.
        if "src_script_type" in signature.parameters:
            _TRANSLITERATOR = XlitEngine(
                src_script_type="indic",
                beam_width=10,
                rescore=False,
            )
            _TRANSLITERATOR_BACKEND = "ai4bharat"
            return _TRANSLITERATOR

        # Older published package versions expose only Roman->Indic helpers,
        # so we intentionally skip them and rely on the native-script fallback.
        _IMPORT_ERRORS["transliteration_ai4bharat"] = (
            f"Unsupported XlitEngine signature: {signature}"
        )
    except ImportError as exc:
        _IMPORT_ERRORS["transliteration_ai4bharat"] = str(exc)
    except Exception as exc:
        _IMPORT_ERRORS["transliteration_ai4bharat"] = str(exc)

    try:
        from indic_transliteration import sanscript

        _TRANSLITERATOR = sanscript
        _TRANSLITERATOR_BACKEND = "indic_transliteration"
        logger.info(
            "Using indic_transliteration fallback for offline Romanization."
        )
        return _TRANSLITERATOR
    except ImportError as exc:
        _IMPORT_ERRORS["transliteration_fallback"] = str(exc)
        if not _TRANSLITERATOR_WARNED:
            logger.warning(
                "No Indic transliteration backend is installed; Indic transcripts will stay in native script."
            )
            _TRANSLITERATOR_WARNED = True
        return None


def _fallback_scheme_for_language(language: str):
    if language in {"hi", "mr", "ne", "sa", "mai"}:
        return "DEVANAGARI"
    if language == "pa":
        return "GURMUKHI"
    if language == "bn":
        return "BENGALI"
    if language in {"or"}:
        return "ORIYA"
    if language == "gu":
        return "GUJARATI"
    if language == "ta":
        return "TAMIL"
    if language == "te":
        return "TELUGU"
    if language == "kn":
        return "KANNADA"
    if language == "ml":
        return "MALAYALAM"
    return None


def _infer_language_from_script(text: str) -> Optional[str]:
    if not text:
        return None

    for char in text:
        codepoint = ord(char)
        if 0x0900 <= codepoint <= 0x097F:
            return "hi"
        if 0x0A00 <= codepoint <= 0x0A7F:
            return "pa"
        if 0x0980 <= codepoint <= 0x09FF:
            return "bn"
        if 0x0B00 <= codepoint <= 0x0B7F:
            return "or"
        if 0x0A80 <= codepoint <= 0x0AFF:
            return "gu"
        if 0x0B80 <= codepoint <= 0x0BFF:
            return "ta"
        if 0x0C00 <= codepoint <= 0x0C7F:
            return "te"
        if 0x0C80 <= codepoint <= 0x0CFF:
            return "kn"
        if 0x0D00 <= codepoint <= 0x0D7F:
            return "ml"
    return None


def _is_mostly_latin(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return True

    latin_letters = 0
    for char in letters:
        if "LATIN" in unicodedata.name(char, ""):
            latin_letters += 1

    return (latin_letters / len(letters)) >= 0.7


def _humanize_itrans(text: str) -> str:
    """Normalise raw ITRANS romanization to a friendlier form.

    Only applies substitutions to tokens that are clearly ITRANS-encoded
    (contain unusual uppercase characters in mid-word position).
    English words and common abbreviations are left intact.
    """
    if not text:
        return text

    # Multi-character substitutions (safe to apply globally)
    _MULTI_CHAR = [
        ("R^I", "ri"),
        ("R^i", "ri"),
        ("~N", "n"),
        ("~n", "n"),
        ("chh", "ch"),
        ("shh", "sh"),
        ("kSh", "ksh"),
        ("GY", "gy"),
    ]

    # Single-character ITRANS substitutions — only apply to tokens that
    # look like ITRANS (mixed case within a short token, not an English word)
    _SINGLE_CHAR = {
        "A": "aa",
        "I": "ee",
        "U": "oo",
        "M": "n",
        "H": "h",
    }

    normalized = text
    for source, target in _MULTI_CHAR:
        normalized = normalized.replace(source, target)

    # Apply single-char substitutions only within tokens that look like
    # ITRANS-encoded Indic words (have internal uppercase letters) and
    # are NOT common English words/abbreviations
    tokens = normalized.split()
    result_tokens = []
    for token in tokens:
        # Skip tokens that are all-uppercase (likely abbreviations: BP, ECG, MRI)
        # or all-lowercase (already clean) or look like normal English
        has_internal_upper = any(
            c.isupper() for c in token[1:] if c.isalpha()
        ) if len(token) > 1 else False

        if has_internal_upper and not token.isupper():
            for source, target in _SINGLE_CHAR.items():
                token = token.replace(source, target)
        result_tokens.append(token)

    normalized = " ".join(result_tokens)
    normalized = re.sub(r"([a-z])\1{2,}", r"\1\1", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def romanize_indic_text(text: str, language: Optional[str]) -> str:
    if not text or _is_mostly_latin(text):
        return text

    normalized_language = normalize_language_code(language)
    if normalized_language not in INDIC_ROMANIZABLE_LANGS:
        return text

    engine = _load_transliterator()
    if engine is None:
        return text

    if _TRANSLITERATOR_BACKEND == "indic_transliteration":
        scheme_name = _fallback_scheme_for_language(normalized_language)
        if not scheme_name:
            return text

        try:
            source_scheme = getattr(engine, scheme_name)
            target_scheme = getattr(engine, "ITRANS")
            romanized = engine.transliterate(text, source_scheme, target_scheme).strip()
            romanized = _humanize_itrans(romanized)
            return romanized or text
        except Exception as exc:
            logger.debug("Fallback Romanization failed for '%s': %s", text, exc)
            return text

    pieces = re.findall(r"\w+|\s+|[^\w\s]", text, flags=re.UNICODE)
    romanized_parts: List[str] = []

    for piece in pieces:
        if not piece.strip():
            romanized_parts.append(piece)
            continue

        if not any(char.isalpha() for char in piece):
            romanized_parts.append(piece)
            continue

        try:
            result = engine.translit_word(piece, lang_code=normalized_language, topk=1)
            if isinstance(result, dict):
                candidates = result.get(normalized_language) or result.get(language) or []
            else:
                candidates = result

            if isinstance(candidates, list) and candidates:
                romanized_parts.append(str(candidates[0]))
            else:
                romanized_parts.append(piece)
        except Exception as exc:
            logger.debug("Romanization failed for token '%s': %s", piece, exc)
            romanized_parts.append(piece)

    romanized = "".join(romanized_parts).strip()
    return romanized or text


def attach_output_variants(text: str, language: Optional[str]) -> Dict[str, Optional[str]]:
    cleaned = (text or "").strip()
    if not cleaned:
        return {
            "text": "",
            "text_native": None,
            "text_romanized": None,
            "language": normalize_language_code(language),
        }

    normalized_language = normalize_language_code(language)

    if TRANSCRIPT_OUTPUT_MODE == "native" or _is_mostly_latin(cleaned):
        return {
            "text": cleaned,
            "text_native": None,
            "text_romanized": None,
            "language": normalized_language,
        }

    romanized = romanize_indic_text(cleaned, normalized_language)
    if not romanized or romanized == cleaned:
        return {
            "text": cleaned,
            "text_native": None,
            "text_romanized": None,
            "language": normalized_language,
        }

    if TRANSCRIPT_OUTPUT_MODE == "both":
        display_text = f"{romanized} [{cleaned}]"
    else:
        display_text = romanized

    return {
        "text": display_text,
        "text_native": cleaned,
        "text_romanized": romanized,
        "language": normalized_language,
    }


def hydrate_transcript_variants(transcript: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hydrated: List[Dict[str, Any]] = []

    for segment in transcript or []:
        payload = dict(segment)
        base_text = (payload.get("text") or "").strip()
        text_native = (payload.get("text_native") or "").strip()
        text_romanized = (payload.get("text_romanized") or "").strip()
        language = normalize_language_code(
            payload.get("language") or _infer_language_from_script(text_native or base_text)
        )

        if not text_native and base_text and not _is_mostly_latin(base_text):
            text_native = base_text
            payload["text_native"] = text_native

        if not text_romanized and text_native:
            text_romanized = romanize_indic_text(text_native, language)
            if text_romanized and text_romanized != text_native:
                payload["text_romanized"] = text_romanized

        hydrated.append(payload)

    return hydrated


def _write_temp_wav(samples, sample_rate: int) -> str:
    temp_path = os.path.join(
        tempfile.gettempdir(),
        f"voice_emr_indic_{uuid.uuid4().hex}.wav",
    )
    sf.write(temp_path, samples, sample_rate, subtype="PCM_16")
    return temp_path


def _slice_audio_for_segments(audio_path: str, diarization_segments: Sequence[Dict]) -> List[Dict[str, Any]]:
    samples, sample_rate = sf.read(audio_path, dtype="float32")
    if getattr(samples, "ndim", 1) > 1:
        samples = samples.mean(axis=1)

    sliced_segments: List[Dict[str, Any]] = []

    for segment in diarization_segments:
        start = max(0.0, float(segment["start"]))
        end = max(start, float(segment["end"]))
        start_index = int(start * sample_rate)
        end_index = int(end * sample_rate)

        if end_index <= start_index:
            continue

        chunk = samples[start_index:end_index]
        if len(chunk) == 0:
            continue

        temp_path = _write_temp_wav(chunk, sample_rate)
        sliced_segments.append(
            {
                "audio_path": temp_path,
                "speaker": segment["speaker"],
                "start": start,
                "end": end,
            }
        )

    return sliced_segments


def transcribe_diarization_segments(
    audio_path: str,
    diarization_segments: Sequence[Dict],
    confidence_fn,
) -> List[Dict[str, Any]]:
    language = selected_indic_language()
    sliced_segments = _slice_audio_for_segments(audio_path, diarization_segments)
    if not sliced_segments:
        return []

    temp_paths = [segment["audio_path"] for segment in sliced_segments]
    try:
        transcripts = transcribe_files_with_indicconformer(temp_paths, language)
    finally:
        for temp_path in temp_paths:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    results: List[Dict[str, Any]] = []
    for segment, raw_text in zip(sliced_segments, transcripts):
        if not raw_text:
            continue

        variants = attach_output_variants(raw_text, language)
        display_text = (variants["text"] or "").strip()
        if not display_text:
            continue

        payload = {
            "speaker": segment["speaker"],
            "start": round(segment["start"], 2),
            "end": round(segment["end"], 2),
            "text": display_text,
            "confidence": confidence_fn(display_text),
            "language": variants["language"],
        }

        if variants.get("text_native"):
            payload["text_native"] = variants["text_native"]
        if variants.get("text_romanized"):
            payload["text_romanized"] = variants["text_romanized"]

        results.append(payload)

    return results


def get_indic_backend_status() -> Dict[str, Any]:
    return {
        "language_hint": selected_indic_language(),
        "multilingual_model": INDIC_MULTILINGUAL_MODEL,
        "loaded_models": list(_INDIC_MODELS.keys()),
        "transcript_output_mode": TRANSCRIPT_OUTPUT_MODE,
        "transliteration_available": _TRANSLITERATOR is not None,
        "transliteration_backend": _TRANSLITERATOR_BACKEND,
        "import_errors": _IMPORT_ERRORS,
    }
