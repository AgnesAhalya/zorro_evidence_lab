# Pilot setup

The local pilot is fully prepared for 10 cases: 5 MuSR and 5 NarraCrime. NarraCrime is stratified into 2 Easy, 2 Medium, and 1 Complex case. GitLab uses the separate 20-case `config/pilot-gitlab.json` validation configuration.

## Files

- `manifest.public.json` contains model-visible case fields and task identities.
- `manifest.private.json` contains controller-only ground truth and assigned suspects.
- `artifacts/simulation/` contains the deterministic local pipeline test.
- `artifacts/adaption/` is created only when live calls are explicitly enabled.

The prompt files live separately in `../prompts/`.

## Commands

Run from the project root:

```text
PYTHONPATH=src python3 -m crimino_flipper.cli show-plan
PYTHONPATH=src python3 -m crimino_flipper.cli build-manifest
PYTHONPATH=src python3 -m crimino_flipper.cli simulate
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The simulation is deterministic and makes no paid requests. Its metrics are plumbing-test values, not study findings.

## Compact results summary

After a run completes, create the short accuracy/flip-rate report with:

```text
python3 scripts/create-results-summary.py \
  --summary pilot/artifacts/adaption/run_summary.json \
  --output pilot/results_summary.md
```

The report contains only the run mode, baseline accuracy, and negative/positive flip-rate percentages.

## Live Adaption run

Install the optional SDK and set the key:

```text
python3 -m pip install -e '.[live]'
export ADAPTION_API_KEY='your-key'
```

The live command requires an explicit paid-call acknowledgement:

```text
PYTHONPATH=src python3 -m crimino_flipper.cli run-live --allow-paid-calls
```

The controller sends full saved history for every branch instead of using provider-side conversation state. This keeps the positive and negative branches independent and reproducible.

All provider calls use temperature 0. Negative investigator messages are generated once and reused unchanged when pressure repetitions are enabled. Positive pressure uses the fixed prompt in `prompts/positive_pressure.txt`; it does not call the investigator model. The repetition count is configurable in JSON and currently defaults to zero.

## Expected calls

- No investigator calls while `follow_up_repetitions` is zero. Set it above zero to enable pressure calls.
- 40 target calls total: 20 × 2 target models × (1 baseline + no pressure repetitions).
- 300 total provider calls before failures or manual reruns.

Every response is saved atomically. Re-running an unchanged task uses its local artifact instead of issuing a duplicate request.
