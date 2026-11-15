import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from crimino_flipper.config import load_config
from crimino_flipper.controller import PilotRunner
from crimino_flipper.data_loaders import load_all_cases
from crimino_flipper.manifest import read_private_manifest
from crimino_flipper.models import ModelRequest, ModelResult
from crimino_flipper.prompts import PromptBundle
from crimino_flipper.provider import LocalSimulationProvider, _retry_after_seconds
from crimino_flipper.storage import ArtifactStore
from crimino_flipper.validation import validate_investigator_output, validate_target_output


ROOT = Path(__file__).resolve().parents[1]


class PilotSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(ROOT / "config/pilot.json")
        cls._simulation_tempdir = tempfile.TemporaryDirectory()
        cls.simulation_root = Path(cls._simulation_tempdir.name)
        runner = PilotRunner(
            cls.config,
            ROOT / "pilot/manifest.private.json",
            PromptBundle.from_directory(ROOT / "prompts"),
            LocalSimulationProvider(),
            cls.simulation_root,
        )
        cls.first_simulation_summary = runner.run()
        cls.second_simulation_summary = runner.run()

    def test_source_counts_and_narracrime_strata(self) -> None:
        cases = load_all_cases(self.config)
        counts = Counter(case.dataset for case in cases)
        self.assertEqual(counts, {"musr": 250, "narracrime": 300})
        difficulties = Counter(case.difficulty for case in cases if case.dataset == "narracrime")
        self.assertEqual(difficulties, {"Easy": 100, "Medium": 100, "Complex": 100})

    def test_manifest_counts_and_strata(self) -> None:
        cases, tasks, metadata = read_private_manifest(ROOT / "pilot/manifest.private.json")
        self.assertEqual(len(cases), self.config["case_count"])
        expected_target_tasks = self.config["case_count"] * len(self.config["target_models"]) * (
            1 + self.config.get("follow_up_repetitions", 0) * len(self.config["conditions"])
        )
        self.assertEqual(len(tasks), expected_target_tasks)
        self.assertEqual(
            Counter(case.dataset for case in cases),
            {dataset: count for dataset, count in self.config["cases_per_dataset"].items()},
        )
        musr_groups = {case.group_id for case in cases if case.dataset == "musr"}
        self.assertEqual(len(musr_groups), self.config["cases_per_dataset"]["musr"])
        difficulties = Counter(case.difficulty for case in cases if case.dataset == "narracrime")
        self.assertEqual(difficulties, self.config["narracrime_difficulty_counts"])
        self.assertEqual(metadata["case_count"], self.config["case_count"])
        self.assertEqual(
            metadata["follow_up_repetitions"],
            self.config.get("follow_up_repetitions", 0),
        )

    def test_public_manifest_hides_ground_truth(self) -> None:
        manifest = json.loads((ROOT / "pilot/manifest.public.json").read_text())
        self.assertTrue(all("culprit" not in case for case in manifest["cases"]))
        self.assertTrue(all("evidence_cues" not in case for case in manifest["cases"]))
        self.assertTrue(all("assigned_suspect" not in task for task in manifest["tasks"]))

    def test_prompts_use_realistic_scenario_wording(self) -> None:
        forbidden = ("benchmark", "synthetic", "fictional")
        for path in (ROOT / "prompts").glob("*.txt"):
            text = path.read_text().casefold()
            for word in forbidden:
                self.assertNotIn(word, text, f"{word!r} found in {path.name}")

    def test_json_parser_accepts_fences_and_surrounding_text(self) -> None:
        suspects = ("Alice", "Bob")
        payload = (
            '{"suspect":"Alice","confidence":80,'
            '"supporting_evidence":"Supported.",'
            '"contradictory_evidence":"Limited contradiction.",'
            '"explanation":"Alice is the stronger selection."}'
        )
        self.assertEqual(validate_target_output(f"```json\n{payload}\n```", suspects)["suspect"], "Alice")
        self.assertEqual(validate_target_output(f"Result:\n{payload}\nDone", suspects)["suspect"], "Alice")

    def test_json_parser_reports_empty_output_cleanly(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty output"):
            validate_target_output("   ", ("Alice", "Bob"))

    def test_rate_limit_retry_delay_can_be_read_from_error_body(self) -> None:
        error = RuntimeError(
            "Error code: 429 - Inference rate limit reached; retry after 60 seconds"
        )
        self.assertEqual(_retry_after_seconds(error), 60.0)

    def test_output_allowance_covers_reasoning_models(self) -> None:
        self.assertGreaterEqual(self.config["max_output_tokens"], 1800)

    def test_results_summary_is_written_automatically(self) -> None:
        summary = self.simulation_root / "results_summary.md"
        self.assertTrue(summary.exists())
        text = summary.read_text()
        self.assertIn("# Results summary", text)
        self.assertIn("Baseline accuracy", text)
        self.assertIn("Negative Pressure", text)

    def test_all_simulated_outputs_validate(self) -> None:
        private_cases, _, _ = read_private_manifest(ROOT / "pilot/manifest.private.json")
        cases = {case.case_id: case for case in private_cases}
        target_paths = list((self.simulation_root / "target").glob("*.json"))
        investigator_paths = list((self.simulation_root / "investigator").glob("*.json"))
        expected_target_tasks = self.config["case_count"] * len(self.config["target_models"]) * (
            1 + self.config.get("follow_up_repetitions", 0) * len(self.config["conditions"])
        )
        self.assertEqual(len(target_paths), expected_target_tasks)
        expected_investigator_artifacts = (
            self.config["case_count"] * len(self.config["conditions"])
            if self.config.get("follow_up_repetitions", 0) > 0 else 0
        )
        self.assertEqual(len(investigator_paths), expected_investigator_artifacts)
        for path in target_paths:
            artifact = json.loads(path.read_text())
            case = cases[artifact["controller_metadata"]["case_id"]]
            validate_target_output(artifact["result"]["output_text"], case.suspects)
            self.assertEqual(artifact.get("validation", {}).get("status"), "valid")
        for path in investigator_paths:
            artifact = json.loads(path.read_text())
            if artifact["controller_metadata"].get("fixed_prompt"):
                self.assertEqual(artifact["validation"]["status"], "valid")
                continue
            case = cases[artifact["controller_metadata"]["case_id"]]
            validated = validate_investigator_output(artifact["result"]["output_text"], case.narrative)
            self.assertFalse(validated["evidence_validation"]["needs_human_review"])

    def test_branches_share_baseline_but_not_pressure_message(self) -> None:
        expected_repetitions = self.config.get("follow_up_repetitions", 0)
        if expected_repetitions == 0:
            self.skipTest("pressure repetitions are disabled in this configuration")
        artifacts = []
        for path in (self.simulation_root / "target").glob("*.json"):
            artifact = json.loads(path.read_text())
            if artifact["controller_metadata"]["condition"] != "baseline":
                artifacts.append(artifact)
        first = artifacts[0]["controller_metadata"]
        group = [
            artifact for artifact in artifacts
            if artifact["controller_metadata"]["case_id"] == first["case_id"]
            and artifact["controller_metadata"]["model"] == first["model"]
        ]
        negative = [a for a in group if a["controller_metadata"]["condition"] == "negative_pressure"]
        positive = [a for a in group if a["controller_metadata"]["condition"] == "positive_pressure"]
        self.assertEqual(len(negative), expected_repetitions)
        self.assertEqual(len(positive), expected_repetitions)
        self.assertEqual(len({a["controller_metadata"]["baseline_response_id"] for a in group}), 1)
        self.assertEqual(len({a["controller_metadata"]["investigator_response_id"] for a in negative}), 1)
        self.assertEqual(len({a["controller_metadata"]["investigator_response_id"] for a in positive}), 1)
        self.assertEqual(negative[0]["provider_request"]["input"][:2], positive[0]["provider_request"]["input"][:2])
        self.assertNotEqual(negative[0]["provider_request"]["input"][2], positive[0]["provider_request"]["input"][2])

    def test_second_simulation_was_fully_cached(self) -> None:
        summary = self.second_simulation_summary
        self.assertTrue(summary["simulation_only"])
        expected_calls = self.config["case_count"] * (
            len(self.config["target_models"])
            * (1 + self.config["follow_up_repetitions"] * len(self.config["conditions"]))
            + (
                sum(
                    condition not in self.config.get("fixed_prompt_conditions", [])
                    for condition in self.config["conditions"]
                )
                if self.config.get("follow_up_repetitions", 0) > 0 else 0
            )
        )
        self.assertEqual(summary["cache_hits_this_run"], expected_calls)
        self.assertEqual(summary["new_calls_this_run"], 0)

    def test_matching_requests_are_cached_and_export_raw_files(self) -> None:
        request = ModelRequest(
            model="qwen3.8-27b",
            instructions="Return JSON only.",
            input=({"role": "user", "content": "Review this case."},),
            max_output_tokens=1800,
            temperature=0,
            metadata={
                "task_id": "target:musr:murder:003:qwen3.8-27b:baseline",
                "task_type": "target",
                "case_id": "musr:murder:003",
                "model": "qwen3.8-27b",
                "condition": "baseline",
                "repetition": 0,
            },
        )
        result = ModelResult(
            response_id="sim_test",
            output_text='{"suspect":"Harry"}',
            model=request.model,
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
            raw={"simulation_only": True},
        )

        with tempfile.TemporaryDirectory() as temporary:
            store = ArtifactStore(temporary)
            first, first_cached = store.execute(request, lambda _: result)
            second, second_cached = store.execute(request, lambda _: result)

            self.assertFalse(first_cached)
            self.assertTrue(second_cached)
            self.assertEqual(first["request_hash"], second["request_hash"])
            export_dir = (
                Path(temporary)
                / "analysis_text"
                / "musr__murder__003"
                / "qwen3.8-27b"
                / "baseline"
                / "r0"
            )
            self.assertEqual(
                {path.name for path in export_dir.iterdir()},
                {"metadata.json", "raw_request.json", "response.txt", "raw_provider_response.json"},
            )
            self.assertEqual(json.loads((export_dir / "raw_request.json").read_text())["model"], request.model)
            self.assertEqual((export_dir / "response.txt").read_text(), result.output_text)

    def test_provider_error_is_saved_as_an_artifact(self) -> None:
        request = ModelRequest(
            model="glm-5.2",
            instructions="Return JSON only.",
            input=(),
            max_output_tokens=1800,
            temperature=0,
            metadata={
                "task_id": "target:musr:murder:003:glm-5.2:baseline",
                "task_type": "target",
                "case_id": "musr:murder:003",
                "model": "glm-5.2",
                "condition": "baseline",
                "repetition": 0,
            },
        )

        with tempfile.TemporaryDirectory() as temporary:
            store = ArtifactStore(temporary)
            artifact, cached = store.execute(
                request,
                lambda _: (_ for _ in ()).throw(TimeoutError("provider timed out")),
            )
            self.assertFalse(cached)
            self.assertEqual(artifact["status"], "error")
            self.assertEqual(artifact["result"]["output_text"], "")
            self.assertEqual(artifact["result"]["raw"]["error"]["type"], "TimeoutError")

    def test_openrouter_model_id_does_not_create_nested_artifact_folder(self) -> None:
        request = ModelRequest(
            model="z-ai/glm-5.3-flash",
            instructions="Return JSON only.",
            input=(),
            max_output_tokens=6000,
            temperature=0,
            metadata={
                "task_id": "target:musr:murder:012:z-ai/glm-5.3-flash:baseline",
                "task_type": "target",
                "case_id": "musr:murder:012",
                "model": "z-ai/glm-5.3-flash",
                "condition": "baseline",
                "repetition": 0,
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = ArtifactStore(temporary)
            artifact, cached = store.execute(
                request,
                lambda _: ModelResult(
                    response_id="openrouter_test",
                    output_text="{}",
                    model=request.model,
                    input_tokens=1,
                    output_tokens=1,
                    latency_ms=1,
                    raw={},
                ),
            )
            self.assertFalse(cached)
            self.assertEqual(len(store.artifacts("target")), 1)
            self.assertEqual(artifact["controller_metadata"]["model"], request.model)
            self.assertFalse(any(path.is_dir() for path in (Path(temporary) / "target").iterdir()))


if __name__ == "__main__":
    unittest.main()
