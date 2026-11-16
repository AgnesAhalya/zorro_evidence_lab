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
        "| Condition | Correct-baseline change | All-baseline change | Majority change | Mean confidence change |",
        "|---|---:|---:|---:|---:|",
    ]
    for condition in ("negative_pressure", "positive_pressure"):
        values = conditions.get(condition, {})
        label = condition.replace("_", " ").title()
        lines.append(
            f"| {label} | {values.get('answer_change_count', 0)}/{values.get('replicate_count', 0)} "
            f"({_percent(values.get('answer_change_rate_initially_correct'))}) | "
            f"{values.get('answer_change_case_count', 0)}/{values.get('answer_change_case_total', 0)} "
            f"({_percent(values.get('answer_change_rate'))}) | "
            f"{values.get('answer_change_case_count', 0)}/{values.get('answer_change_case_total', 0)} "
            f"({_percent(values.get('majority_answer_change_rate'))}) | "
            f"{values.get('mean_confidence_change_all', '—')} points |"
        )
    lines.extend(
        [
            "",
            "The first column conditions on initially correct baseline answers. "
            "The second and third columns include all valid baseline answers, regardless of baseline accuracy. "
            "An em dash means no valid paired observations were available.",
            "",
        ]
    )
    return "\n".join(lines)


def write_results_summary(data: dict, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_results_summary(data), encoding="utf-8")
