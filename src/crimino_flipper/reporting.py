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
        "| Condition | Flip rate | Majority-case flip rate |",
        "|---|---:|---:|",
    ]
    for condition in ("negative_pressure", "positive_pressure"):
        values = conditions.get(condition, {})
        label = condition.replace("_", " ").title()
        lines.append(
            f"| {label} | {_percent(values.get('replicate_flip_rate'))} | "
            f"{_percent(values.get('majority_case_flip_rate'))} |"
        )
    lines.extend(
        [
            "",
            "Percentages use valid, paired responses only. An em dash means no valid paired observations were available.",
            "",
        ]
    )
    return "\n".join(lines)


def write_results_summary(data: dict, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_results_summary(data), encoding="utf-8")
