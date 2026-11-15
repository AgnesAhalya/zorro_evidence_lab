import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .manifest import read_private_manifest
from .models import Case, ModelRequest, ModelResult, PilotTask
from .prompts import PromptBundle
from .provider import Provider
from .reporting import write_results_summary
from .scoring import score_simulation
from .storage import ArtifactStore
from .validation import (
    first_source_sentence,
    validate_investigator_output,
    validate_response_status,
    validate_target_output,
)


class PilotRunner:
    def __init__(self, config: dict, manifest_path: str | Path, prompts: PromptBundle,
                 provider: Provider, artifacts_root: str | Path):
        self.config = config
        self.cases, self.tasks, self.manifest_metadata = read_private_manifest(manifest_path)
        configured_repetitions = config.get("follow_up_repetitions", 0)
        manifest_repetitions = self.manifest_metadata.get("follow_up_repetitions")
        if manifest_repetitions is not None and manifest_repetitions != configured_repetitions:
            raise ValueError(
                "Manifest/config mismatch: follow_up_repetitions changed; "
                "run build-manifest before starting the run"
            )
        manifest_conditions = self.manifest_metadata.get("conditions")
        if manifest_conditions is not None and manifest_conditions != list(config["conditions"]):
            raise ValueError(
                "Manifest/config mismatch: conditions changed; "
                "run build-manifest before starting the run"
            )
        self.case_by_id = {case.case_id: case for case in self.cases}
        self.prompts = prompts
        self.provider = provider
        self.store = ArtifactStore(artifacts_root)
        self.invalid_outputs: list[dict[str, str]] = []
        self.skipped_tasks = 0
        self.progress_total = 0
        self.progress_completed = 0

    def _request(self, model: str, instructions: str, messages: list[dict[str, str]],
                 metadata: dict, temperature: float) -> ModelRequest:
        return ModelRequest(
            model=model,
            instructions=instructions,
            input=tuple(messages),
            max_output_tokens=self.config["max_output_tokens"],
            temperature=temperature,
            metadata=metadata,
        )

    def _report_progress(self, phase: str, current_task: str | None = None,
                         task_status: str = "completed") -> None:
        self.progress_completed += 1
        total = max(self.progress_total, 1)
        percent = round(min(self.progress_completed / total * 100, 100), 1)
        status = {
            "run_id": self.config["run_id"],
            "status": "running",
            "phase": phase,
            "task_status": task_status,
            "completed_work_items": self.progress_completed,
            "total_work_items": self.progress_total,
            "progress_percent": percent,
            "current_task": current_task,
            "cache_hits_this_run": self.store.cache_hits,
            "new_calls_this_run": self.store.cache_misses,
            "invalid_output_count": len(self.invalid_outputs),
            "skipped_follow_up_tasks": self.skipped_tasks,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        (self.store.root / "run_status.json").write_text(
            json.dumps(status, indent=2), encoding="utf-8"
        )
        if self.config.get("execution", {}).get("progress_reporting", True):
            print(
                f"[progress] {percent:5.1f}% "
                f"({self.progress_completed}/{self.progress_total}) "
                f"phase={phase} status={task_status} task={current_task or '-'}",
                flush=True,
            )

    def _investigator_messages(self) -> dict[tuple[str, str], dict]:
        messages: dict[tuple[str, str], dict] = {}
        if self.config.get("follow_up_repetitions", 0) <= 0:
            return messages
        for case in self.cases:
            incorrect = next(name for name in case.suspects if name != case.culprit)
            for condition in self.config["conditions"]:
                assigned = incorrect if condition == "negative_pressure" else case.culprit
                task_id = f"investigator:{case.case_id}:{condition}"
                if condition in self.config.get("fixed_prompt_conditions", []):
                    fixed_prompt = self.prompts.positive_pressure_for(assigned)
                    request = self._request(
                        "fixed-positive-prompt",
                        "Return the fixed investigator message exactly as supplied.",
                        [{"role": "user", "content": fixed_prompt}],
                        {
                            "task_id": task_id,
                            "task_type": "investigator",
                            "case_id": case.case_id,
                            "condition": condition,
                            "model": "fixed-positive-prompt",
                            "assigned_suspect": assigned,
                            "exact_source_claim": None,
                            "fixed_prompt": True,
                        },
                        self.config["investigator_temperature"],
                    )
                    response_id = "fixed_" + hashlib.sha256(fixed_prompt.encode()).hexdigest()[:20]
                    result = ModelResult(
                        response_id=response_id,
                        output_text=fixed_prompt,
                        model="fixed-positive-prompt",
                        input_tokens=0,
                        output_tokens=0,
                        latency_ms=0,
                        raw={"fixed_prompt": True, "simulation_only": True},
                    )
                    artifact, _ = self.store.write_static(request, result)
                    messages[(case.case_id, condition)] = {
                        "response_id": artifact["result"]["response_id"],
                        "message": fixed_prompt,
                        "cited_claims": [],
                    }
                    self._report_progress("investigator", task_id, "fixed")
                    continue
                request = self._request(
                    self.config["investigator_model"],
                    "Return only the requested JSON object.",
                    [{"role": "user", "content": self.prompts.investigator_for(case, assigned)}],
                    {
                        "task_id": task_id,
                        "task_type": "investigator",
                        "case_id": case.case_id,
                        "condition": condition,
                        "model": self.config["investigator_model"],
                        "assigned_suspect": assigned,
                    "exact_source_claim": first_source_sentence(case.narrative),
                    },
                    self.config["investigator_temperature"],
                )
                artifact, _ = self.store.execute(request, self.provider.create_response)
                try:
                    validate_response_status(artifact)
                    validated = validate_investigator_output(
                        artifact["result"]["output_text"], case.narrative
                    )
                except ValueError as exc:
                    self.store.record_validation(request, "invalid", str(exc))
                    self.invalid_outputs.append({"task_id": task_id, "error": str(exc)})
                    self._report_progress("investigator", task_id, "invalid")
                    continue
                self.store.record_validation(request, "valid")
                messages[(case.case_id, condition)] = {
                    "response_id": artifact["result"]["response_id"],
                    **validated,
                }
                self._report_progress("investigator", task_id)
        return messages

    def _baseline(self, case: Case, task: PilotTask) -> tuple[dict, dict] | None:
        baseline_prompt = self.prompts.baseline_for(case)
        task_id = f"target:{case.case_id}:{task.target_model}:baseline"
        request = self._request(
            task.target_model,
            self.prompts.system,
            [{"role": "user", "content": baseline_prompt}],
            {
                "task_id": task_id,
                "task_type": "target",
                "case_id": case.case_id,
                "model": task.target_model,
                "condition": "baseline",
                "repetition": 0,
                "suspects": case.suspects,
                "culprit": case.culprit,
                "assigned_suspect": None,
            },
            self.config["target_temperature"],
        )
        artifact, _ = self.store.execute(request, self.provider.create_response)
        try:
            validate_response_status(artifact)
            parsed = validate_target_output(artifact["result"]["output_text"], case.suspects)
        except ValueError as exc:
            self.store.record_validation(request, "invalid", str(exc))
            self.invalid_outputs.append({"task_id": task_id, "error": str(exc)})
            return None
        self.store.record_validation(request, "valid")
        return artifact, parsed

    def run(self) -> dict:
        self.store.cache_hits = 0
        self.store.cache_misses = 0
        self.invalid_outputs = []
        self.skipped_tasks = 0
        investigator_work = (
            len(self.cases) * len(self.config["conditions"])
            if self.config.get("follow_up_repetitions", 0) > 0 else 0
        )
        self.progress_total = len(self.tasks) + investigator_work
        self.progress_completed = 0
        (self.store.root / "run_status.json").write_text(
            json.dumps({
                "run_id": self.config["run_id"],
                "status": "running",
                "phase": "starting",
                "completed_work_items": 0,
                "total_work_items": self.progress_total,
                "progress_percent": 0.0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2),
            encoding="utf-8",
        )
        investigator_messages = self._investigator_messages()
        baselines: dict[tuple[str, str], tuple[dict, dict]] = {}
        for task in (task for task in self.tasks if task.condition == "baseline"):
            case = self.case_by_id[task.case_id]
            baseline = self._baseline(case, task)
            baseline_task_id = f"target:{case.case_id}:{task.target_model}:baseline"
            if baseline is not None:
                baselines[(case.case_id, task.target_model)] = baseline
                self._report_progress("baseline", baseline_task_id)
            else:
                self._report_progress("baseline", baseline_task_id, "invalid")

        for task in (task for task in self.tasks if task.condition != "baseline"):
            case = self.case_by_id[task.case_id]
            task_id = f"target:{case.case_id}:{task.target_model}:{task.condition}:r{task.repetition}"
            if (case.case_id, task.target_model) not in baselines:
                self.skipped_tasks += 1
                self._report_progress("follow_up", task_id, "skipped")
                continue
            if (case.case_id, task.condition) not in investigator_messages:
                self.skipped_tasks += 1
                self._report_progress("follow_up", task_id, "skipped")
                continue
            baseline_artifact, baseline_value = baselines[(case.case_id, task.target_model)]
            investigator = investigator_messages[(case.case_id, task.condition)]
            request = self._request(
                task.target_model,
                self.prompts.system,
                [
                    {"role": "user", "content": self.prompts.baseline_for(case)},
                    {"role": "assistant", "content": baseline_artifact["result"]["output_text"]},
                    {"role": "user", "content": investigator["message"]},
                ],
                {
                    "task_id": task_id,
                    "task_type": "target",
                    "case_id": case.case_id,
                    "model": task.target_model,
                    "condition": task.condition,
                    "repetition": task.repetition,
                    "suspects": case.suspects,
                    "culprit": case.culprit,
                    "assigned_suspect": task.assigned_suspect,
                    "baseline_suspect": baseline_value["suspect"],
                    "baseline_response_id": baseline_artifact["result"]["response_id"],
                    "investigator_response_id": investigator["response_id"],
                },
                self.config["target_temperature"],
            )
            artifact, _ = self.store.execute(request, self.provider.create_response)
            try:
                validate_response_status(artifact)
                validate_target_output(artifact["result"]["output_text"], case.suspects)
            except ValueError as exc:
                self.store.record_validation(request, "invalid", str(exc))
                self.invalid_outputs.append({"task_id": task_id, "error": str(exc)})
                self._report_progress("follow_up", task_id, "invalid")
                continue
            self.store.record_validation(request, "valid")
            self._report_progress("follow_up", task_id)

        metrics = score_simulation(self.store, self.config["pricing_credits_per_million_tokens"])
        all_artifacts = self.store.artifacts("investigator") + self.store.artifacts("target")
        summary = {
            "run_id": self.config["run_id"],
            "simulation_only": all(
                artifact["result"]["raw"].get("simulation_only", False)
                for artifact in all_artifacts
            ),
            "case_count": len(self.cases),
            "investigator_artifacts": len(self.store.artifacts("investigator")),
            "target_artifacts": len(self.store.artifacts("target")),
            "cache_hits_this_run": self.store.cache_hits,
            "new_calls_this_run": self.store.cache_misses,
            "invalid_output_count": len(self.invalid_outputs),
            "invalid_outputs": self.invalid_outputs,
            "skipped_follow_up_tasks": self.skipped_tasks,
            "metrics": metrics,
        }
        (self.store.root / "run_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        write_results_summary(summary, self.store.root / "results_summary.md")
        (self.store.root / "run_status.json").write_text(
            json.dumps({
                "run_id": self.config["run_id"],
                "status": "completed",
                "phase": "complete",
                "completed_work_items": self.progress_completed,
                "total_work_items": self.progress_total,
                "progress_percent": 100.0,
                "cache_hits_this_run": self.store.cache_hits,
                "new_calls_this_run": self.store.cache_misses,
                "invalid_output_count": len(self.invalid_outputs),
                "skipped_follow_up_tasks": self.skipped_tasks,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2),
            encoding="utf-8",
        )
        return summary
