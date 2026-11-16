from pathlib import Path


def _percent(value: object) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%"


def build_results_summary(data: dict) -> str:
    metrics = data.get("metrics", {})
    conditions = metrics.get("conditions", {})
    mode = "Simulation" if metrics.get("simulation_only") else "Live run"
    lines = [
        "# Results summary",
        "",
        f"**Run:** `{data.get('run_id', 'unknown')}`  ",
        f"**Mode:** {mode}",
        "",
        "## Accuracy",
        "",
        "| Measure | Percentage |",
        "|---|---:|",
        f"| Baseline accuracy | {_percent(metrics.get('baseline_accuracy'))} |",
        "",
        "## Flip rate",
        "",
        "| Condition | Initial accuracy | Post-pressure accuracy | Correct → incorrect | Incorrect → correct | Mean confidence change |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for condition in ("negative_pressure", "positive_pressure"):
        values = conditions.get(condition, {})
        label = condition.replace("_", " ").title()
        lines.append(
            f"| {label} | {_percent(values.get('initial_accuracy'))} | "
            f"{_percent(values.get('post_pressure_accuracy'))} | "
            f"{values.get('correct_to_incorrect_count', 0)}/{values.get('correct_to_incorrect_total', 0)} | "
            f"{values.get('incorrect_to_correct_count', 0)}/{values.get('incorrect_to_correct_total', 0)} | "
            f"{values.get('mean_confidence_change_all', '—')} points |"
        )
    lines.extend(
        [
            "",
            "Accuracy and transition counts use valid paired baseline/pressure responses. "
            "With one repetition, majority analysis is identical to the single pressure response. "
            "An em dash means no valid paired observations were available.",
            "",
        ]
    )
    return "\n".join(lines)


def write_results_summary(data: dict, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_results_summary(data), encoding="utf-8")
