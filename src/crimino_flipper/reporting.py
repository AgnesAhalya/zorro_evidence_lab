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
        "| Condition | Flip rate | Majority-case flip rate | Answer-change rate |",
        "|---|---:|---:|---:|",
    ]
    for condition in ("negative_pressure", "positive_pressure"):
        values = conditions.get(condition, {})
        label = condition.replace("_", " ").title()
        lines.append(
            f"| {label} | {_percent(values.get('replicate_flip_rate'))} | "
            f"{_percent(values.get('majority_case_flip_rate'))} | "
            f"{_percent(values.get('answer_change_rate'))} |"
        )
    epistemic_balance = metrics.get("epistemic_balance", {})
    lines.extend(
        [
            "",
            "## EpistemicBalance",
            "",
            "| Measure | Negative pressure | Positive pressure | Positive − negative |",
            "|---|---:|---:|---:|",
            f"| Investigator-preference alignment | {conditions.get('negative_pressure', {}).get('suggestion_adoption_count', 0)}/{conditions.get('negative_pressure', {}).get('suggestion_adoption_total', 0)} "
            f"({_percent(epistemic_balance.get('negative_suggestion_adoption_rate'))}) | "
            f"{conditions.get('positive_pressure', {}).get('suggestion_adoption_count', 0)}/{conditions.get('positive_pressure', {}).get('suggestion_adoption_total', 0)} "
            f"({_percent(epistemic_balance.get('positive_suggestion_adoption_rate'))}) | "
            f"{_percent(epistemic_balance.get('suggestion_adoption_rate_difference_positive_minus_negative'))} |",
            f"| Directional accuracy transition | {conditions.get('negative_pressure', {}).get('correct_to_incorrect_count', 0)}/{conditions.get('negative_pressure', {}).get('correct_to_incorrect_total', 0)} harmful "
            f"({_percent(epistemic_balance.get('negative_harmful_transition_rate'))}) | "
            f"{conditions.get('positive_pressure', {}).get('incorrect_to_correct_count', 0)}/{conditions.get('positive_pressure', {}).get('incorrect_to_correct_total', 0)} corrective "
            f"({_percent(epistemic_balance.get('positive_corrective_transition_rate'))}) | "
            f"{_percent(epistemic_balance.get('corrective_minus_harmful_transition_rate'))} |",
            f"| Mean confidence change | {conditions.get('negative_pressure', {}).get('confidence_changed_count', 0)}/{conditions.get('negative_pressure', {}).get('confidence_change_observation_count', 0)} changed; "
            f"{conditions.get('negative_pressure', {}).get('mean_confidence_change_all', '—')} points | "
            f"{conditions.get('positive_pressure', {}).get('confidence_changed_count', 0)}/{conditions.get('positive_pressure', {}).get('confidence_change_observation_count', 0)} changed; "
            f"{conditions.get('positive_pressure', {}).get('mean_confidence_change_all', '—')} points | "
            f"{epistemic_balance.get('confidence_change_difference_positive_minus_negative', '—')} points |",
            "",
            "Definitions: Investigator-preference alignment is the share of responses whose final suspect matches the suspect emphasized by the investigator message. "
            "Directional accuracy transition is the share of initially correct responses made incorrect under negative pressure, or initially incorrect responses made correct under positive pressure. "
            "Mean confidence change is pressure confidence minus baseline confidence, measured in points. "
            "Positive − negative values are percentage-point or point differences, not additional cases. "
            "Selecting the reference culprit under positive pressure is not, by itself, evidence of independent evidence-based reasoning.",
            "",
            "## Accuracy transitions",
            "",
            "| Condition | Initial accuracy | Post-pressure accuracy | Correct → incorrect | Incorrect → correct | Mean confidence change |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
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
    coverage = data.get("coverage", {})
    any_model = coverage.get("at_least_one_model_valid", {})
    both_models = coverage.get("both_target_models_valid", {})
    lines.extend(
        [
            "",
            "## Model-wise variation",
            "",
            "| Model | Condition | Initial accuracy | Post-pressure accuracy | Correct → incorrect | Incorrect → correct | Answer-change rate | Mean confidence change |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for model, model_values in sorted(data.get("model_metrics", {}).items()):
        for condition in ("negative_pressure", "positive_pressure"):
            values = model_values.get("conditions", {}).get(condition, {})
            label = condition.replace("_", " ").title()
            lines.append(
                f"| `{model}` | {label} | {_percent(values.get('initial_accuracy'))} | "
                f"{_percent(values.get('post_pressure_accuracy'))} | "
                f"{values.get('correct_to_incorrect_count', 0)}/{values.get('correct_to_incorrect_total', 0)} | "
                f"{values.get('incorrect_to_correct_count', 0)}/{values.get('incorrect_to_correct_total', 0)} | "
                f"{_percent(values.get('answer_change_rate'))} | "
                f"{values.get('mean_confidence_change', '—')} points |"
            )
    lines.extend(
        [
            "",
            "## Case coverage",
            "",
            "| Stage | At least one model valid | Both target models valid |",
            "|---|---:|---:|",
            f"| Total cases | {coverage.get('total_cases', '—')} | {coverage.get('total_cases', '—')} |",
            f"| Baseline | {any_model.get('baseline', '—')} | {both_models.get('baseline', '—')} |",
            f"| Baseline + negative pressure | {any_model.get('baseline_negative', '—')} | {both_models.get('baseline_negative', '—')} |",
            f"| Baseline + positive pressure | {any_model.get('baseline_positive', '—')} | {both_models.get('baseline_positive', '—')} |",
            f"| Baseline + negative + positive | {any_model.get('complete_three_stage', '—')} | {both_models.get('complete_three_stage', '—')} |",
            f"| Missing negative after baseline | {coverage.get('at_least_one_model_missing_negative_after_baseline', '—')} | — |",
            f"| Missing positive after baseline | {coverage.get('at_least_one_model_missing_positive_after_baseline', '—')} | — |",
            "",
            "Coverage counts are case-level. The first column counts a case when at least one target model has a valid response; the second requires valid responses from both target models.",
        ]
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
