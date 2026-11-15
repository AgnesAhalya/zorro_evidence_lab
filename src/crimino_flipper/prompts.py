import json
from dataclasses import dataclass
from pathlib import Path

from .models import Case


def render(template: str, **values: object) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("Prompt has unresolved template variables")
    return rendered


@dataclass(frozen=True)
class PromptBundle:
    system: str
    baseline: str
    investigator: str
    positive_pressure: str

    @classmethod
    def from_directory(cls, directory: str | Path) -> "PromptBundle":
        root = Path(directory)
        return cls(
            system=(root / "shared_system.txt").read_text(encoding="utf-8").strip(),
            baseline=(root / "baseline.txt").read_text(encoding="utf-8").strip(),
            investigator=(root / "investigator.txt").read_text(encoding="utf-8").strip(),
            positive_pressure=(root / "positive_pressure.txt").read_text(encoding="utf-8").strip(),
        )

    def baseline_for(self, case: Case) -> str:
        return render(
            self.baseline,
            narrative=case.narrative,
            question=case.question,
            suspects_json=json.dumps(case.suspects, ensure_ascii=False),
        )

    def investigator_for(self, case: Case, assigned_suspect: str) -> str:
        return render(
            self.investigator,
            narrative=case.narrative,
            suspects_json=json.dumps(case.suspects, ensure_ascii=False),
            assigned_suspect=assigned_suspect,
        )

    def positive_pressure_for(self, assigned_suspect: str) -> str:
        return render(self.positive_pressure, assigned_suspect=assigned_suspect)
