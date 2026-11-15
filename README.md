# Crimino Flipper pilot

This repository contains the complete 10-case local pilot setup for studying how investigator pressure changes model decisions in realistic, controlled case reviews.

## Pilot composition

- 5 MuSR cases from distinct paired-scenario groups.
- 5 NarraCrime cases: 2 Easy, 2 Medium, and 1 Complex.
- Target models: `glm-5.2` and `qwen3.5-397b`, configured in `config/pilot.json`.
- Investigator model: `glm-53-flash`.
- One baseline plus a configurable number of negative- and positive-pressure responses per target model and case. The JSON configs currently set zero repetitions; omitted settings also default to zero.
- Positive pressure uses a fixed prompt and does not make an investigator-model call.
- 300 total provider calls before failures or manual reruns.

## Local verification

```text
PYTHONPATH=src python3 -m crimino_flipper.cli show-plan
PYTHONPATH=src python3 -m crimino_flipper.cli build-manifest
PYTHONPATH=src python3 -m crimino_flipper.cli simulate
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The simulator is deterministic and does not call Adaption. Simulated metrics only verify the experiment plumbing and are not research findings.

See [`pilot/README.md`](pilot/README.md) for live-run instructions and artifact locations. Prompts are maintained independently in [`prompts/`](prompts/).

The 10-case local pilot is configured in `config/pilot.json`. GitLab validation and its manual pilot job use `config/pilot-gitlab.json` with 20 cases. The full 550-case experiment is configured separately in `config/main.json`. Paid calls are not part of automatic CI validation.

## Docker and GitLab

The entire setup can run inside Docker:

```text
docker compose run --rm plan
docker compose run --rm simulate
docker compose run --rm test
```

GitLab CI configuration builds and validates the project without making paid Adaption calls. See [`docs/docker-gitlab.md`](docs/docker-gitlab.md) for container publishing and the explicitly enabled live workflow.

## Dataset attribution and licensing

This project uses the following datasets for AI evaluation, including running evaluations and publishing evaluation results:

- **MuSR**, from [`TAUR-Lab/MuSR`](https://huggingface.co/datasets/TAUR-Lab/MuSR), using the `murder_mysteries` split. The project configuration identifies this material as **CC BY 4.0**.
- **NarraCrime**, from [`Cosinecos/EVAR`](https://github.com/Cosinecos/EVAR). The project configuration identifies this material as **CC BY 4.0**.

The datasets are used under the [Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/). Attribution is provided here; any redistributed or adapted dataset-derived material should retain attribution, link to the license, and identify changes where applicable.
