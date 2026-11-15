from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Case:
    case_id: str
    dataset: str
    narrative: str
    question: str
    suspects: tuple[str, ...]
    culprit: str
    difficulty: str | None = None
    source_locator: str | None = None
    source_revision: str | None = None
    group_id: str | None = None
    evidence_cues: tuple[str, ...] = ()

    def public_view(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("culprit", None)
        data.pop("evidence_cues", None)
        return data

    def private_view(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PilotTask:
    case_id: str
    target_model: str
    condition: str
    repetition: int
    assigned_suspect: str | None = None


@dataclass(frozen=True)
class ModelRequest:
    model: str
    instructions: str
    input: tuple[dict[str, str], ...]
    max_output_tokens: int
    temperature: float
    metadata: dict[str, Any]

    def provider_payload(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "instructions": self.instructions,
            "input": list(self.input),
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "store": False,
            "tools": [],
            "tool_choice": "none",
            "agentic_memory": False,
        }


@dataclass(frozen=True)
class ModelResult:
    response_id: str
    output_text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw: dict[str, Any]

