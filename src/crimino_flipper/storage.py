import hashlib
import json
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .models import ModelRequest, ModelResult


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache_hits = 0
        self.cache_misses = 0

    @staticmethod
    def request_hash(request: ModelRequest) -> str:
        cache_identity = {
            "provider_payload": request.provider_payload(),
            "task_id": request.metadata["task_id"],
        }
        encoded = json.dumps(cache_identity, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(encoded).hexdigest()

    def path_for(self, request: ModelRequest) -> Path:
        task_id = request.metadata["task_id"].replace(":", "__")
        return self.root / request.metadata["task_type"] / f"{task_id}.json"

    @staticmethod
    def _write_atomic(path: Path, artifact: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            json.dump(artifact, handle, indent=2, ensure_ascii=False)
            temporary = Path(handle.name)
        temporary.replace(path)

    @staticmethod
    def _safe_component(value: object) -> str:
        return str(value).replace("/", "_").replace(":", "__")

    @staticmethod
    def _write_text_atomic(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(text)
            temporary = Path(handle.name)
        temporary.replace(path)

    def _write_text_bundle(self, request: ModelRequest, artifact: dict) -> None:
        metadata = artifact["controller_metadata"]
        case_id = self._safe_component(metadata["case_id"])
        model = self._safe_component(metadata["model"])
        condition = self._safe_component(metadata["condition"])
        if metadata["task_type"] == "target":
            repetition = metadata.get("repetition", 0)
            run_dir = self.root / "analysis_text" / case_id / model / condition / f"r{repetition}"
        else:
            run_dir = self.root / "analysis_text" / case_id / model / f"investigator_{condition}"

        metadata_payload = {
            key: value
            for key, value in artifact.items()
            if key not in {"provider_request", "result"}
        }
        request_payload = artifact.get("provider_request", request.provider_payload())
        result = artifact.get("result", {})
        response_text = result.get("output_text", "")
        raw_response = result.get("raw", {})

        self._write_text_atomic(
            run_dir / "metadata.json",
            json.dumps(metadata_payload, indent=2, ensure_ascii=False) + "\n",
        )
        self._write_text_atomic(
            run_dir / "raw_request.json",
            json.dumps(request_payload, indent=2, ensure_ascii=False) + "\n",
        )
        self._write_text_atomic(run_dir / "response.txt", response_text)
        self._write_text_atomic(
            run_dir / "raw_provider_response.json",
            json.dumps(raw_response, indent=2, ensure_ascii=False) + "\n",
        )

    def execute(
        self,
        request: ModelRequest,
        call: Callable[[ModelRequest], ModelResult],
    ) -> tuple[dict, bool]:
        path = self.path_for(request)
        expected_hash = self.request_hash(request)
        if path.exists():
            artifact = json.loads(path.read_text(encoding="utf-8"))
            if artifact["request_hash"] == expected_hash:
                self.cache_hits += 1
                self._write_text_bundle(request, artifact)
                return artifact, True
            raise RuntimeError(f"Request changed for existing artifact: {path}")

        started = datetime.now(timezone.utc)
        try:
            result = call(request)
        except Exception as exc:
            result = ModelResult(
                response_id="error_" + expected_hash[:20],
                output_text="",
                model=request.model,
                input_tokens=0,
                output_tokens=0,
                latency_ms=round((datetime.now(timezone.utc) - started).total_seconds() * 1000),
                raw={
                    "status": "error",
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                },
            )
        provider_status = result.raw.get("status", "completed")
        artifact = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": provider_status,
            "error": result.raw.get("error"),
            "validation": {"status": "pending", "error": None},
            "request_hash": expected_hash,
            "task_id": request.metadata["task_id"],
            "task_type": request.metadata["task_type"],
            "controller_metadata": request.metadata,
            "provider_request": request.provider_payload(),
            "result": asdict(result),
        }
        self._write_atomic(path, artifact)
        self._write_text_bundle(request, artifact)
        self.cache_misses += 1
        return artifact, False

    def write_static(self, request: ModelRequest, result: ModelResult) -> tuple[dict, bool]:
        """Persist a deterministic local prompt without counting it as a provider call."""
        path = self.path_for(request)
        expected_hash = self.request_hash(request)
        if path.exists():
            artifact = json.loads(path.read_text(encoding="utf-8"))
            if artifact["request_hash"] == expected_hash:
                self._write_text_bundle(request, artifact)
                return artifact, True
            raise RuntimeError(f"Request changed for existing artifact: {path}")

        artifact = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": result.raw.get("status", "completed"),
            "error": result.raw.get("error"),
            "validation": {"status": "valid", "error": None},
            "request_hash": expected_hash,
            "task_id": request.metadata["task_id"],
            "task_type": request.metadata["task_type"],
            "controller_metadata": request.metadata,
            "provider_request": request.provider_payload(),
            "result": asdict(result),
        }
        self._write_atomic(path, artifact)
        self._write_text_bundle(request, artifact)
        return artifact, False

    def record_validation(
        self, request: ModelRequest, status: str, error: str | None = None
    ) -> None:
        path = self.path_for(request)
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["validation"] = {"status": status, "error": error}
        self._write_atomic(path, artifact)
        self._write_text_bundle(request, artifact)

    def artifacts(self, task_type: str) -> list[dict]:
        directory = self.root / task_type
        if not directory.exists():
            return []
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]
