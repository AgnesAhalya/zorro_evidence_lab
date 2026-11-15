import hashlib
import json
from pathlib import Path
from typing import Iterable

from .models import Case, PilotTask


def stable_case_order(cases: Iterable[Case]) -> list[Case]:
    return sorted(cases, key=lambda c: hashlib.sha256(c.case_id.encode()).hexdigest())


def choose_pilot_cases(
    cases: Iterable[Case],
    per_dataset: dict[str, int],
    narracrime_difficulty_counts: dict[str, int] | None = None,
    distinct_musr_groups: bool = True,
) -> list[Case]:
    grouped: dict[str, list[Case]] = {}
    for case in stable_case_order(cases):
        grouped.setdefault(case.dataset, []).append(case)
    selected: list[Case] = []
    for dataset, count in per_dataset.items():
        available = grouped.get(dataset, [])
        if len(available) < count:
            raise ValueError(f"{dataset}: need {count} cases, found {len(available)}")
        if dataset == "musr" and distinct_musr_groups:
            distinct_groups: list[Case] = []
            seen_groups: set[str | None] = set()
            for case in available:
                if case.group_id in seen_groups:
                    continue
                seen_groups.add(case.group_id)
                distinct_groups.append(case)
                if len(distinct_groups) == count:
                    break
            if len(distinct_groups) != count:
                raise ValueError(f"musr: need {count} distinct scenario groups")
            selected.extend(distinct_groups)
        elif dataset == "narracrime" and narracrime_difficulty_counts:
            stratified: list[Case] = []
            for difficulty, difficulty_count in narracrime_difficulty_counts.items():
                matching = [case for case in available if case.difficulty == difficulty]
                if len(matching) < difficulty_count:
                    raise ValueError(
                        f"narracrime/{difficulty}: need {difficulty_count}, found {len(matching)}"
                    )
                stratified.extend(matching[:difficulty_count])
            if len(stratified) != count:
                raise ValueError("NarraCrime difficulty counts do not equal requested case count")
            selected.extend(stratified)
        else:
            selected.extend(available[:count])
    return sorted(selected, key=lambda c: c.case_id)


def build_tasks(cases: Iterable[Case], config: dict) -> list[PilotTask]:
    tasks: list[PilotTask] = []
    for case in cases:
        incorrect = next(s for s in case.suspects if s != case.culprit)
        for model in config["target_models"]:
            tasks.append(PilotTask(case.case_id, model, "baseline", 0))
            for condition in config["conditions"]:
                assigned = incorrect if condition == "negative_pressure" else case.culprit
                # Keep the number of pressure calls configurable in JSON.  A
                # A missing value is intentionally conservative: no pressure
                # repetitions, rather than silently expanding a paid run.
                for repetition in range(1, config.get("follow_up_repetitions", 0) + 1):
                    tasks.append(PilotTask(case.case_id, model, condition, repetition, assigned))
    return tasks


def write_manifests(
    public_path: str | Path,
    private_path: str | Path,
    cases: list[Case],
    tasks: list[PilotTask],
    metadata: dict,
) -> None:
    public_output = {
        "metadata": metadata,
        "cases": [case.public_view() for case in cases],
        "tasks": [
            {key: value for key, value in task.__dict__.items() if key != "assigned_suspect"}
            for task in tasks
        ],
    }
    private_output = {
        "metadata": metadata,
        "cases": [case.private_view() for case in cases],
        "tasks": [task.__dict__ for task in tasks],
    }
    for path, output in ((Path(public_path), public_output), (Path(private_path), private_output)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, indent=2), encoding="utf-8")


def read_private_manifest(path: str | Path) -> tuple[list[Case], list[PilotTask], dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = [
        Case(
            **{
                **item,
                "suspects": tuple(item["suspects"]),
                "evidence_cues": tuple(item.get("evidence_cues", [])),
            }
        )
        for item in data["cases"]
    ]
    tasks = [PilotTask(**item) for item in data["tasks"]]
    return cases, tasks, data["metadata"]

