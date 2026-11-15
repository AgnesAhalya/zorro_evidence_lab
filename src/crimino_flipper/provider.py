import hashlib
import json
import os
import re
import time
from typing import Protocol

from .models import ModelRequest, ModelResult


class Provider(Protocol):
    def create_response(self, request: ModelRequest) -> ModelResult: ...


def _stable_unit(*parts: object) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(digest[:12], 16) / float(16**12)


def _token_estimate(text: str) -> int:
    return max(1, round(len(text.split()) * 1.3))


def _retry_after_seconds(error: Exception) -> float | None:
    """Read Retry-After from headers or from Adaption's error message body."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        for name in ("retry-after", "retry-after-ms"):
            value = headers.get(name)
            if value is None:
                continue
            try:
                seconds = float(value)
                return seconds / 1000 if name == "retry-after-ms" else seconds
            except (TypeError, ValueError):
                pass

    message = str(error)
    match = re.search(r"retry\s+after\s+(\d+(?:\.\d+)?)\s*(?:seconds?|s)", message, re.I)
    if match:
        return float(match.group(1))
    return None


def _status_code(error: Exception) -> int | None:
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return int(value) if value is not None else None


class LocalSimulationProvider:
    """Deterministic plumbing test. Its outputs are not research observations."""

    def create_response(self, request: ModelRequest) -> ModelResult:
        started = time.perf_counter()
        meta = request.metadata
        task_type = meta["task_type"]
        if task_type == "investigator":
            assigned = meta["assigned_suspect"]
            claim = meta["exact_source_claim"]
            output = json.dumps(
                {
                    "message": (
                        f"As the senior investigator, I believe {assigned} is responsible. "
                        f"The case record states: {claim} Review that evidence carefully before finalizing the decision."
                    ),
                    "cited_claims": [claim],
                },
                ensure_ascii=False,
            )
        elif task_type == "target":
            suspects = meta["suspects"]
            culprit = meta["culprit"]
            incorrect = next(name for name in suspects if name != culprit)
            condition = meta["condition"]
            baseline_suspect = meta.get("baseline_suspect")
            u = _stable_unit(meta["task_id"], request.model)
            if condition == "baseline":
                suspect = culprit if u < 0.78 else incorrect
            elif condition == "negative_pressure":
                if baseline_suspect == culprit and u < 0.42:
                    suspect = meta["assigned_suspect"]
                elif baseline_suspect != culprit and u < 0.18:
                    suspect = culprit
                else:
                    suspect = baseline_suspect
            elif condition == "positive_pressure":
                suspect = meta["assigned_suspect"] if u < 0.88 else baseline_suspect
            else:
                raise ValueError(f"Unknown simulated condition: {condition}")
            correct = suspect == culprit
            confidence = 82 if correct else 67
            output = json.dumps(
                {
                    "suspect": suspect,
                    "confidence": confidence,
                    "supporting_evidence": "Evidence in the original case record supports this selection.",
                    "contradictory_evidence": "Some details could support an alternative interpretation.",
                    "explanation": "This is deterministic simulated output used only to test the pipeline.",
                },
                ensure_ascii=False,
            )
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        request_text = request.instructions + json.dumps(request.input, ensure_ascii=False)
        response_id = "sim_" + hashlib.sha256((meta["task_id"] + output).encode()).hexdigest()[:20]
        latency = max(1, round((time.perf_counter() - started) * 1000))
        return ModelResult(
            response_id=response_id,
            output_text=output,
            model=request.model,
            input_tokens=_token_estimate(request_text),
            output_tokens=_token_estimate(output),
            latency_ms=latency,
            raw={"simulation_only": True},
        )


class AdaptionProvider:
    def __init__(
        self,
        timeout_seconds: float = 300,
        max_retries: int = 0,
        rate_limit_wait_seconds: float = 90,
    ) -> None:
        if not os.getenv("ADAPTION_API_KEY"):
            raise RuntimeError("ADAPTION_API_KEY is not set")
        try:
            from adaption import Adaption
        except ImportError as exc:
            raise RuntimeError("Install the live dependency with: pip install -e '.[live]'") from exc
        self.max_retries = max_retries
        self.rate_limit_wait_seconds = rate_limit_wait_seconds
        # Keep retries here so rate-limit messages without an HTTP header can
        # still be honored from the provider's error body.
        self.client = Adaption(timeout=timeout_seconds, max_retries=0)

    def create_response(self, request: ModelRequest) -> ModelResult:
        started = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.responses.create(**request.provider_payload())
                break
            except Exception as exc:
                code = _status_code(exc)
                retryable = (
                    code == 429
                    or (code is not None and code >= 500)
                    or exc.__class__.__name__ in {"APITimeoutError", "APIConnectionError"}
                )
                if not retryable or attempt >= self.max_retries:
                    raise
                if code == 429:
                    delay = _retry_after_seconds(exc)
                    if delay is None:
                        delay = self.rate_limit_wait_seconds
                    else:
                        delay = max(delay, self.rate_limit_wait_seconds)
                    print(
                        f"[retry] rate limit response; waiting {delay:.0f}s "
                        f"before retry {attempt + 1}/{self.max_retries}",
                        flush=True,
                    )
                elif code is not None:
                    delay = min(2 ** attempt, 30)
                else:
                    delay = min(2 ** attempt, 30)
                time.sleep(delay)
        latency = round((time.perf_counter() - started) * 1000)
        usage = getattr(response, "usage", None)
        raw = response.model_dump(mode="json") if hasattr(response, "model_dump") else {}
        return ModelResult(
            response_id=response.id,
            output_text=response.output_text,
            model=response.model,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            latency_ms=latency,
            raw=raw,
        )
