#!/usr/bin/env python3
"""Merge five OpenRouter shard summaries into one run summary."""

import argparse
import csv
import json
import tempfile
from pathlib import Path

from crimino_flipper.config import load_config
from crimino_flipper.reporting import write_results_summary
from crimino_flipper.scoring import score_simulation
from crimino_flipper.storage import ArtifactStore
from crimino_flipper.validation import validate_target_output


def _write_case_analysis(root: Path, output_dir: Path) -> None:
    """Write one row per case/model/pressure response from uploaded text."""
    targets = {}
    for metadata_path in sorted(root.glob("**/analysis_text/**/metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("task_type") != "target":
            continue
        controller = metadata["controller_metadata"]
        response_path = metadata_path.parent / "response.txt"
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
        try:
            parsed = validate_target_output(response, tuple(controller["suspects"]))
        except (ValueError, TypeError):
            parsed = None
        key = (controller["case_id"], controller["model"], controller["condition"], controller.get("repetition", 0))
        targets[key] = (controller, parsed)

    baselines = {
        (case_id, model): parsed
        for (case_id, model, condition, _), (_, parsed) in targets.items()
        if condition == "baseline" and parsed is not None
    }
    rows = []
    for (case_id, model, condition, repetition), (controller, parsed) in targets.items():
        if condition == "baseline":
            continue
        baseline = baselines.get((case_id, model))
        baseline_suspect = baseline["suspect"] if baseline else ""
        baseline_confidence = baseline["confidence"] if baseline else ""
        pressure_suspect = parsed["suspect"] if parsed else ""
        pressure_confidence = parsed["confidence"] if parsed else ""
        rows.append({
            "case_id": case_id,
            "model": model,
            "condition": condition,
            "repetition": repetition,
            "culprit": controller.get("culprit", ""),
            "baseline_suspect": baseline_suspect,
            "baseline_correct": bool(baseline and baseline_suspect == controller.get("culprit")),
            "pressure_suspect": pressure_suspect,
            "answer_changed": bool(baseline and parsed and pressure_suspect != baseline_suspect),
            "correctness_flip": bool(
                baseline and parsed and baseline_suspect == controller.get("culprit")
                and pressure_suspect != controller.get("culprit")
            ),
            "baseline_confidence": baseline_confidence,
            "pressure_confidence": pressure_confidence,
            "confidence_change": (
                pressure_confidence - baseline_confidence if baseline and parsed else ""
            ),
            "suggested_suspect": controller.get("assigned_suspect", ""),
            "suggestion_adopted": bool(
                parsed and controller.get("assigned_suspect")
                and pressure_suspect == controller.get("assigned_suspect")
            ),
            "valid_response": parsed is not None,
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "case_analysis.csv"
    fields = list(rows[0]) if rows else ["case_id"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _model_breakdown(case_analysis_path: Path) -> dict:
    """Calculate paired accuracy and transition metrics for each model."""
    rows = list(csv.DictReader(case_analysis_path.open(encoding="utf-8")))
    result = {}
    for model in sorted({row["model"] for row in rows}):
        model_rows = [row for row in rows if row["model"] == model]
        conditions = {}
        baseline_by_case = {
            row["case_id"]: row["baseline_correct"] == "True"
            for row in model_rows if row["valid_response"] == "True"
        }
        for condition in ("negative_pressure", "positive_pressure"):
            paired = [
                row for row in model_rows
                if row["condition"] == condition and row["valid_response"] == "True"
            ]
            before = [row["baseline_correct"] == "True" for row in paired]
            after = [row["pressure_suspect"] == row["culprit"] for row in paired]
            changed = [row["answer_changed"] == "True" for row in paired]
            confidence = [float(row["confidence_change"]) for row in paired if row["confidence_change"]]
            conditions[condition] = {
                "paired_count": len(paired),
                "initial_accuracy": sum(before) / len(before) if before else None,
                "post_pressure_accuracy": sum(after) / len(after) if after else None,
                "correct_to_incorrect_count": sum(a and not b for a, b in zip(before, after)),
                "correct_to_incorrect_total": sum(before),
                "incorrect_to_correct_count": sum(not a and b for a, b in zip(before, after)),
                "incorrect_to_correct_total": len(before) - sum(before),
                "answer_change_count": sum(changed),
                "answer_change_rate": sum(changed) / len(changed) if changed else None,
                "mean_confidence_change": sum(confidence) / len(confidence) if confidence else None,
            }
        result[model] = {
            "baseline_accuracy": sum(baseline_by_case.values()) / len(baseline_by_case) if baseline_by_case else None,
            "baseline_case_count": len(baseline_by_case),
            "conditions": conditions,
        }
    return result


def _recompute_metrics_from_text(root: Path, config: dict) -> dict:
    """Re-score uploaded analysis text without contacting a provider."""
    metadata_paths = sorted(root.glob("**/analysis_text/**/metadata.json"))
    if not metadata_paths:
        raise ValueError("No uploaded analysis_text metadata found for offline re-scoring")
    with tempfile.TemporaryDirectory() as temporary:
        combined = Path(temporary)
        for metadata_path in metadata_paths:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            task_type = metadata.get("task_type")
            if task_type not in {"target", "investigator"}:
                continue
            response_path = metadata_path.parent / "response.txt"
            response_text = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
            task_id = str(metadata["task_id"]).replace("/", "_").replace(":", "__")
            artifact = {
                "controller_metadata": metadata["controller_metadata"],
                "result": {
                    "output_text": response_text,
                    "model": metadata["controller_metadata"].get("model", ""),
                    "raw": {},
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
            }
            output = combined / task_type / f"{task_id}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(artifact), encoding="utf-8")
        return score_simulation(
            ArtifactStore(combined), config["pricing_credits_per_million_tokens"]
        )


def _case_coverage(root: Path, config: dict, total_cases: int) -> dict:
    """Count case-level response coverage from saved target responses."""
    valid: dict[str, dict[str, set[str]]] = {}
    for metadata_path in sorted(root.glob("**/analysis_text/**/metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("task_type") != "target":
            continue
        controller = metadata["controller_metadata"]
        response_path = metadata_path.parent / "response.txt"
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
        try:
            validate_target_output(response, tuple(controller["suspects"]))
        except (ValueError, TypeError):
            continue
        valid.setdefault(controller["case_id"], {}).setdefault(controller["condition"], set()).add(controller["model"])

    def count_cases(required: set[str], strict: bool = False) -> int:
        count = 0
        for case_id in valid:
            if all(
                len(valid[case_id].get(condition, set())) >= (len(config["target_models"]) if strict else 1)
                for condition in required
            ):
                count += 1
        return count

    any_model = {
        "baseline": count_cases({"baseline"}),
        "baseline_negative": count_cases({"baseline", "negative_pressure"}),
        "baseline_positive": count_cases({"baseline", "positive_pressure"}),
        "complete_three_stage": count_cases({"baseline", "negative_pressure", "positive_pressure"}),
    }
    both_models = {
        "baseline": count_cases({"baseline"}, strict=True),
        "baseline_negative": count_cases({"baseline", "negative_pressure"}, strict=True),
        "baseline_positive": count_cases({"baseline", "positive_pressure"}, strict=True),
        "complete_three_stage": count_cases({"baseline", "negative_pressure", "positive_pressure"}, strict=True),
    }
    return {
        "total_cases": total_cases,
        "at_least_one_model_valid": any_model,
        "both_target_models_valid": both_models,
        "at_least_one_model_missing_negative_after_baseline": total_cases - any_model["baseline_negative"],
        "at_least_one_model_missing_positive_after_baseline": total_cases - any_model["baseline_positive"],
    }


def _weighted(values: list[tuple[float | None, int]]) -> float | None:
    usable = [(value, count) for value, count in values if value is not None and count]
    denominator = sum(count for _, count in usable)
    return sum(value * count for value, count in usable) / denominator if denominator else None


def merge(
    config_path: str,
    summary_paths: list[Path],
    output_dir: Path,
    summary_root: Path,
) -> dict:
    config = load_config(config_path)
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in summary_paths]
    if not summaries:
        raise ValueError("No shard summaries found")
    expected_run = config["run_id"]
    if any(item.get("run_id") != expected_run for item in summaries):
        raise ValueError("Shard run IDs do not match the active configuration")

    model_count = len(config["target_models"])
    baseline_counts = [item["case_count"] * model_count for item in summaries]
    metrics = [item.get("metrics", {}) for item in summaries]
    merged_conditions = {}
    for condition in ("negative_pressure", "positive_pressure"):
        rows = [metric.get("conditions", {}).get(condition, {}) for metric in metrics]
        replicate_counts = [int(row.get("replicate_count", 0)) for row in rows]
        paired_counts = [int(row.get("paired_replicate_count", 0)) for row in rows]
        merged_conditions[condition] = {
            "replicate_flip_rate": _weighted(
                [(row.get("replicate_flip_rate"), count) for row, count in zip(rows, replicate_counts)]
            ),
            "majority_case_flip_rate": _weighted(
                [(row.get("majority_case_flip_rate"), count) for row, count in zip(rows, replicate_counts)]
            ),
            "mean_confidence_change": _weighted(
                [(row.get("mean_confidence_change"), count) for row, count in zip(rows, replicate_counts)]
            ),
            "answer_change_rate": _weighted(
                [(row.get("answer_change_rate"), count) for row, count in zip(rows, paired_counts)]
            ),
            "answer_change_rate_initially_correct": _weighted(
                [(row.get("answer_change_rate_initially_correct"), count) for row, count in zip(rows, replicate_counts)]
            ),
            "majority_answer_change_rate": _weighted(
                [(row.get("majority_answer_change_rate"), count) for row, count in zip(rows, paired_counts)]
            ),
            "answer_change_count": sum(int(row.get("answer_change_count", 0)) for row in rows),
            "answer_change_count_initially_correct": sum(
                int(row.get("answer_change_count_initially_correct", 0)) for row in rows
            ),
            "answer_change_replicate_count": sum(paired_counts),
            "mean_confidence_change_all": _weighted(
                [(row.get("mean_confidence_change_all"), count) for row, count in zip(rows, paired_counts)]
            ),
            "replicate_count": sum(replicate_counts),
            "paired_replicate_count": sum(paired_counts),
        }

    # Recompute from the uploaded response text so new analysis definitions
    # can be applied to an already-paid run without making provider calls.
    merged_metrics = _recompute_metrics_from_text(summary_root, config)
    coverage = _case_coverage(summary_root, config, sum(item.get("case_count", 0) for item in summaries))
    merged = {
        "run_id": expected_run,
        "shard_count": len(summaries),
        "case_count": sum(item.get("case_count", 0) for item in summaries),
        "investigator_artifacts": sum(item.get("investigator_artifacts", 0) for item in summaries),
        "target_artifacts": sum(item.get("target_artifacts", 0) for item in summaries),
        "cache_hits_this_run": sum(item.get("cache_hits_this_run", 0) for item in summaries),
        "new_calls_this_run": sum(item.get("new_calls_this_run", 0) for item in summaries),
        "invalid_output_count": sum(item.get("invalid_output_count", 0) for item in summaries),
        "invalid_outputs": [error for item in summaries for error in item.get("invalid_outputs", [])],
        "skipped_follow_up_tasks": sum(item.get("skipped_follow_up_tasks", 0) for item in summaries),
        "coverage": coverage,
        "model_metrics": {},
        "metrics": merged_metrics,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_case_analysis(summary_root, output_dir)
    merged["model_metrics"] = _model_breakdown(output_dir / "case_analysis.csv")
    (output_dir / "run_summary.json").write_text(json.dumps(merged, indent=2), encoding="utf-8")
    write_results_summary(merged, output_dir / "results_summary.md")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.summary_root)
    # GitHub may add an artifact-name directory or preserve the uploaded path.
    # Discover summaries recursively rather than assuming one layout.
    paths = sorted(
        path
        for path in root.glob("**/run_summary.json")
        if any(part.startswith("shard-") for part in path.parts)
        or "shard-" in path.as_posix()
    )
    if len(paths) != 5:
        raise ValueError(f"Expected 5 shard summaries, found {len(paths)}")
    print(json.dumps(merge(args.config, paths, Path(args.output_dir), root), indent=2))


if __name__ == "__main__":
    main()
