import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .controller import PilotRunner
from .data_loaders import load_all_cases
from .manifest import build_tasks, choose_pilot_cases, write_manifests
from .prompts import PromptBundle
from .provider import AdaptionProvider, LocalSimulationProvider


DEFAULT_CONFIG = "config/pilot.json"
DEFAULT_PUBLIC_MANIFEST = "pilot/manifest.public.json"
DEFAULT_PRIVATE_MANIFEST = "pilot/manifest.private.json"


def show_plan(config: dict) -> dict:
    cases = config["case_count"]
    models = len(config["target_models"])
    # Default to no pressure calls so a config omission cannot accidentally
    # create a paid follow-up run.
    repetitions = config.get("follow_up_repetitions", 0)
    conditions = len(config["conditions"])
    target_calls = cases * models * (1 + repetitions * conditions)
    fixed_conditions = set(config.get("fixed_prompt_conditions", []))
    investigator_calls = (
        cases * sum(condition not in fixed_conditions for condition in config["conditions"])
        if repetitions > 0 else 0
    )
    return {
        "cases": cases,
        "target_model_calls": target_calls,
        "investigator_calls": investigator_calls,
        "total_calls": target_calls + investigator_calls,
        "dry_run_default": config["execution"]["dry_run_default"],
    }


def build_manifest(config: dict, public_path: str, private_path: str) -> dict:
    all_cases = load_all_cases(config)
    selected = choose_pilot_cases(
        all_cases,
        config["cases_per_dataset"],
        config["narracrime_difficulty_counts"],
        config.get("distinct_musr_groups", True),
    )
    tasks = build_tasks(selected, config)
    metadata = {
        "run_id": config["run_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection": (
            "sha256(case_id) deterministic ordering; distinct MuSR scenario groups; "
            "NarraCrime difficulty strata"
        ),
        "case_count": len(selected),
        "target_task_count": len(tasks),
        "follow_up_repetitions": config.get("follow_up_repetitions", 0),
        "conditions": list(config["conditions"]),
        "target_models": list(config["target_models"]),
        "source_revisions": {
            name: source["revision"] for name, source in config["sources"].items()
        },
        "prompt_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path("prompts").glob("*.txt"))
        },
    }
    write_manifests(public_path, private_path, selected, tasks, metadata)
    return metadata


def manifest_matches_config(config: dict, manifest_path: str | Path) -> bool:
    path = Path(manifest_path)
    if not path.exists():
        return False
    try:
        metadata = json.loads(path.read_text(encoding="utf-8")).get("metadata", {})
    except (OSError, json.JSONDecodeError):
        return False
    expected_prompts = {
        prompt.name: hashlib.sha256(prompt.read_bytes()).hexdigest()
        for prompt in sorted(Path("prompts").glob("*.txt"))
    }
    return (
        metadata.get("run_id") == config["run_id"]
        and metadata.get("case_count") == config["case_count"]
        and metadata.get("follow_up_repetitions", 0)
        == config.get("follow_up_repetitions", 0)
        and metadata.get("conditions") == list(config["conditions"])
        and metadata.get("target_models") == list(config["target_models"])
        and metadata.get("source_revisions")
        == {name: source["revision"] for name, source in config["sources"].items()}
        and metadata.get("prompt_sha256") == expected_prompts
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and run a configured case evaluation.")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show-plan", help="Show expected call counts")

    build = sub.add_parser("build-manifest", help="Build public and private pilot manifests")
    build.add_argument("--public", default=DEFAULT_PUBLIC_MANIFEST)
    build.add_argument("--private", default=DEFAULT_PRIVATE_MANIFEST)

    simulate = sub.add_parser("simulate", help="Run the full local simulation")
    simulate.add_argument("--manifest", default=DEFAULT_PRIVATE_MANIFEST)
    simulate.add_argument("--artifacts", default="pilot/artifacts/simulation")

    live = sub.add_parser("run-live", help="Run paid Adaption calls")
    live.add_argument("--manifest", default=DEFAULT_PRIVATE_MANIFEST)
    live.add_argument("--artifacts", default="pilot/artifacts/adaption")
    live.add_argument(
        "--allow-paid-calls",
        action="store_true",
        help="Required acknowledgement that this command makes paid API calls",
    )
    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "show-plan":
        print(json.dumps(show_plan(config), indent=2))
        return
    if args.command == "build-manifest":
        print(json.dumps(build_manifest(config, args.public, args.private), indent=2))
        return

    manifest = Path(args.manifest)
    if not manifest_matches_config(config, manifest):
        print(
            f"Manifest {manifest} is missing or stale; rebuilding it from the active config.",
            file=sys.stderr,
        )
        build_manifest(config, DEFAULT_PUBLIC_MANIFEST, str(manifest))
    prompts = PromptBundle.from_directory("prompts")
    if args.command == "simulate":
        provider = LocalSimulationProvider()
    else:
        if not args.allow_paid_calls:
            parser.error("run-live requires --allow-paid-calls")
        execution = config.get("execution", {})
        provider = AdaptionProvider(
            timeout_seconds=execution.get("request_timeout_seconds", 300),
            max_retries=execution.get("max_retries", 0),
            rate_limit_wait_seconds=execution.get("rate_limit_wait_seconds", 90),
        )
    runner = PilotRunner(config, manifest, prompts, provider, args.artifacts)
    print(json.dumps(runner.run(), indent=2))


if __name__ == "__main__":
    main()
