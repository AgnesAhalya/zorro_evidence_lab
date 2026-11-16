# Zorro Evidence Lab

Zorro Evidence Lab evaluates how large language models revise suspect identifications when an investigator applies misleading or evidence-consistent conversational pressure. The evidence, case question, and baseline reasoning context remain unchanged across the pressure branches.

## Study overview

- **Cases:** 550 structured investigative cases: 250 MuSR cases and 300 NarraCrime cases.
- **Pilot:** 10 cases: 5 MuSR and 5 NarraCrime.
- **Target models in the reported OpenRouter run:** `qwen/qwen3.7-flash` and `z-ai/glm-5.3-flash`.
- **Investigator model for negative-pressure messages:** `openai/gpt-oss-20b` in the OpenRouter configuration.
- **Temperature:** `0` for all calls.
- **Conditions:** one baseline response, one negative-pressure response, and one positive-pressure response per target model and case in the reported run.
- **Positive pressure:** a fixed prompt; it does not require an investigator-model call.
- **Negative pressure:** one generated investigator message per case, validated and reused across target models.
- **Default repetition behavior:** no follow-up repetition when the setting is omitted; the reported run explicitly uses `follow_up_repetitions: 1`.

The evaluation reports baseline accuracy, accuracy-conditioned flips, incorrect-to-correct recovery, answer changes, confidence changes, investigator-preference alignment, and EpistemicBalance. Invalid responses and missing dependent follow-ups are reported separately and are not silently counted as incorrect predictions.

## Main-run call plan

With 550 cases, two target models, and one response per pressure condition:

| Call type | Count |
|---|---:|
| Baseline target calls | 1,100 |
| Negative-pressure target calls | 1,100 |
| Positive-pressure target calls | 1,100 |
| Negative-pressure investigator calls | 550 |
| **Total provider calls** | **3,850** |

The 10-case pilot has 70 provider calls under the same design. Counts are generated from JSON configuration rather than hardcoded in CI.

## Reported main-run findings

- Overall baseline accuracy was **86.5%**.
- Negative pressure changed **166/942** initially correct responses to incorrect suspects (**17.6%**); no initially incorrect responses became correct in that condition.
- Positive pressure changed **143/149** initially incorrect responses to the correct suspect (**96.0%**) and produced no correct-to-incorrect transitions.
- Investigator-preference alignment was **28.8%** under negative pressure and **99.5%** under positive pressure. Alignment with a correct suggestion is not proof of independent reasoning.
- Mean confidence change was **-0.098 points** under negative pressure and **+3.955 points** under positive pressure.

These are valid paired-response results from the recovered main run; invalid and missing responses are reported separately.

## Verification

```text
PYTHONPATH=src python3 -m compileall -q src
PYTHONPATH=src python3 -m unittest discover -s tests -v
docker compose build plan
docker compose run --rm plan
docker compose run --rm test
docker compose run --rm simulate
```

Simulation and validation do not make paid provider calls. Live runs require an explicit paid-call flag and a provider key supplied through the environment. Never commit or print `ADAPTION_API_KEY` or `OPENROUTER_API_KEY`.

## Running a live experiment

The manual GitHub Actions workflow supports separate pilot and main runs for OpenRouter and Adaption. Select the desired scope, provide the matching protected repository secret, and explicitly authorize paid calls. The workflow is not started automatically by tests or Docker validation.

For local Docker execution, see [`docs/docker-gitlab.md`](docs/docker-gitlab.md). For the research protocol, see [`docs/experimental-design.md`](docs/experimental-design.md). Prompt behavior is documented in [`docs/prompts.md`](docs/prompts.md), and software execution details are in [`docs/execution-plan.md`](docs/execution-plan.md).

## Results and figures

Recovered main-run results and separate publication figures are stored in [`adaption_github_results/`](adaption_github_results/). The figures are generated from the saved run summary by [`scripts/create_adaption_visualizations.py`](scripts/create_adaption_visualizations.py). No new provider calls are required to regenerate them.

## Dataset attribution and licensing

This project uses the following public sources for model evaluation:

- **MuSR**, from [`TAUR-Lab/MuSR`](https://huggingface.co/datasets/TAUR-Lab/MuSR), using the `murder_mysteries` split. The project configuration identifies this material as **CC BY 4.0**.
- **NarraCrime**, from [`Cosinecos/EVAR`](https://github.com/Cosinecos/EVAR). The project configuration identifies this material as **CC BY 4.0**.

The sources are used under the [Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/). Redistributed or adapted dataset-derived material should retain attribution, link to the license, and identify changes where applicable.
