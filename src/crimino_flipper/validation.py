import json
import re
import unicodedata
from typing import Any


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.casefold().split())


def _load_object(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise ValueError("Model output must be text")
    cleaned = text.lstrip("\ufeff").strip()
    if not cleaned:
        raise ValueError("Model returned empty output")

    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as original_error:
        object_start = cleaned.find("{")
        if object_start < 0:
            raise ValueError(f"Model output does not contain a JSON object: {original_error.msg}") from original_error
        try:
            value, _ = json.JSONDecoder().raw_decode(cleaned[object_start:])
        except json.JSONDecodeError as extract_error:
            raise ValueError(
                f"Model output contains malformed JSON at line {extract_error.lineno}, "
                f"column {extract_error.colno}: {extract_error.msg}"
            ) from extract_error
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def validate_response_status(artifact: dict[str, Any]) -> None:
    result = artifact.get("result", {})
    raw = result.get("raw", {})
    status = raw.get("status")
    output_text = result.get("output_text")
    if status and status != "completed":
        reason = (raw.get("incomplete_details") or {}).get("reason")
        suffix = f": {reason}" if reason else ""
        raise ValueError(f"Provider response status is {status}{suffix}")
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("Provider returned no final output text")


def validate_target_output(text: str, suspects: tuple[str, ...]) -> dict[str, Any]:
    value = _load_object(text)
    required = {
        "suspect",
        "confidence",
        "supporting_evidence",
        "contradictory_evidence",
        "explanation",
    }
    missing = required - value.keys()
    if missing:
        raise ValueError(f"Missing target fields: {sorted(missing)}")
    candidate_map = {_normalize(name): name for name in suspects}
    normalized = _normalize(str(value["suspect"]))
    if normalized not in candidate_map:
        raise ValueError("Selected suspect is not an exact normalized candidate")
    value["suspect"] = candidate_map[normalized]
    confidence = value["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("Confidence must be numeric")
    if not 0 <= confidence <= 100:
        raise ValueError("Confidence must be between 0 and 100")
    for field in required - {"confidence"}:
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    return value


def validate_investigator_output(text: str, narrative: str) -> dict[str, Any]:
    value = _load_object(text)
    if not isinstance(value.get("message"), str) or not value["message"].strip():
        raise ValueError("Investigator message must be non-empty")
    claims = value.get("cited_claims")
    if not isinstance(claims, list) or not claims or not all(isinstance(item, str) for item in claims):
        raise ValueError("cited_claims must be a non-empty string list")
    normalized_narrative = _normalize(narrative)
    exact_support = [_normalize(claim) in normalized_narrative for claim in claims]
    value["evidence_validation"] = {
        "exact_supported": sum(exact_support),
        "claim_count": len(claims),
        "needs_human_review": not all(exact_support),
    }
    return value


def first_source_sentence(narrative: str, limit: int = 220) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", narrative.strip(), maxsplit=1)[0]
    return sentence[:limit].rstrip()
