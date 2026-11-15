import ast
import csv
import json
from pathlib import Path

from .models import Case


def _validate_case(case: Case) -> None:
    if not case.narrative.strip():
        raise ValueError(f"{case.case_id}: empty narrative")
    if len(case.suspects) < 2:
        raise ValueError(f"{case.case_id}: fewer than two suspects")
    if len(set(case.suspects)) != len(case.suspects):
        raise ValueError(f"{case.case_id}: duplicate suspect names")
    if case.culprit not in case.suspects:
        raise ValueError(f"{case.case_id}: culprit not in suspect list")


def load_musr(csv_path: str | Path, revision: str) -> list[Case]:
    path = Path(csv_path)
    cases: list[Case] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            choices = tuple(str(value).strip() for value in ast.literal_eval(row["choices"]))
            answer_index = int(row["answer_index"])
            culprit = row["answer_choice"].strip()
            if choices[answer_index] != culprit:
                raise ValueError(f"MuSR row {index}: answer index and answer choice disagree")
            case = Case(
                case_id=f"musr:murder:{index:03d}",
                dataset="musr",
                narrative=row["narrative"].strip(),
                question=row["question"].strip(),
                suspects=choices,
                culprit=culprit,
                source_locator=f"{path.as_posix()}#row={index}",
                source_revision=revision,
                group_id=f"musr:pair:{index // 2:03d}",
            )
            _validate_case(case)
            cases.append(case)
    if len(cases) != 250:
        raise ValueError(f"Expected 250 MuSR murder cases, found {len(cases)}")
    return cases


def load_narracrime(root: str | Path, revision: str) -> list[Case]:
    root_path = Path(root)
    cases: list[Case] = []
    annotations = sorted(root_path.glob("*_Cases/*/annotation.json"))
    for annotation_path in annotations:
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        case_dir = annotation_path.parent
        narrative = (case_dir / annotation["input_file"]).read_text(encoding="utf-8").strip()
        suspects = tuple(item["name"].strip() for item in annotation["suspects"])
        case = Case(
            case_id=f"narracrime:{annotation['case_id']}",
            dataset="narracrime",
            narrative=narrative,
            question="Who is most likely responsible for the incident described in this case?",
            suspects=suspects,
            culprit=annotation["culprit"].strip(),
            difficulty=annotation["split"],
            source_locator=annotation_path.as_posix(),
            source_revision=revision,
            evidence_cues=tuple(annotation.get("evidence_cues", [])),
        )
        _validate_case(case)
        cases.append(case)
    if len(cases) != 300:
        raise ValueError(f"Expected 300 NarraCrime cases, found {len(cases)}")
    return cases


def load_all_cases(config: dict) -> list[Case]:
    musr = config["sources"]["musr"]
    narra = config["sources"]["narracrime"]
    return load_musr(musr["local_path"], musr["revision"]) + load_narracrime(
        narra["local_path"], narra["revision"]
    )
