#!/usr/bin/env python3
"""Merge five OpenRouter shard summaries into one run summary."""

import argparse
import json
from pathlib import Path

from crimino_flipper.config import load_config
from crimino_flipper.reporting import write_results_summary


def _weighted(values: list[tuple[float | None, int]]) -> float | None:
    usable = [(value, count) for value, count in values if value is not None and count]
    denominator = sum(count for _, count in usable)
    return sum(value * count for value, count in usable) / denominator if denominator else None


def merge(config_path: str, summary_paths: list[Path], output_dir: Path) -> dict:
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
            "replicate_count": sum(replicate_counts),
        }

    merged_metrics = {
        "simulation_only": all(metric.get("simulation_only", False) for metric in metrics),
        "valid_target_responses": sum(metric.get("valid_target_responses", 0) for metric in metrics),
        "invalid_target_responses": sum(metric.get("invalid_target_responses", 0) for metric in metrics),
        "baseline_accuracy": _weighted(
            [(metric.get("baseline_accuracy"), count) for metric, count in zip(metrics, baseline_counts)]
        ),
        "initially_correct_baselines": sum(
            metric.get("initially_correct_baselines", 0) for metric in metrics
        ),
        "estimated_credits": round(sum(metric.get("estimated_credits", 0) for metric in metrics), 6),
        "conditions": merged_conditions,
    }
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
        "metrics": merged_metrics,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
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
    paths = sorted(root.glob("**/shard-*/run_summary.json"))
    print(json.dumps(merge(args.config, paths, Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
