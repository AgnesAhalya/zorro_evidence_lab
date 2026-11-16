# Docker and GitLab

## Local Docker workflow

These commands are offline unless the live profile is explicitly selected:

```text
docker compose build plan
docker compose run --rm plan
docker compose run --rm test
docker compose run --rm simulate
```

Simulation artifacts are mounted to `pilot/artifacts/` on the host. Matching cached responses may be reused during local simulation, but simulation does not make provider calls.

## Live provider workflow

The live service is excluded from ordinary Docker Compose runs. It requires the `live` profile, a provider key, and the explicit paid-call flag:

```text
export ADAPTION_API_KEY='your-key'
docker compose --profile live run --rm adaption-pilot
```

The key must be supplied through the environment or `.env`; it must never be committed or printed. OpenRouter runs use the corresponding OpenRouter service/configuration and `OPENROUTER_API_KEY`.

Do not run the live service automatically from tests, image builds, or simulations.

## GitLab pipeline

`.gitlab-ci.yml` validates the configured experiment sizes and contains four stages:

1. `validate`: prepares pinned data, prints plans, builds manifests, runs offline simulation, and runs tests.
2. `container`: builds the image and runs plan and test commands inside it.
3. `publish`: on the default branch, publishes commit-tagged and `latest` images to the GitLab Container Registry.
4. `experiment`: exposes separate manual pilot and main live jobs.

The case counts and call plans come from JSON configuration:

| Configuration | Cases | Provider calls with one repetition |
|---|---:|---:|
| `config/pilot.json` | 10 | 70 |
| `config/pilot-gitlab.json` | 20 | 140 |
| `config/main.json` | 550 | 3,850 |

Each count assumes two target models, one baseline response, one negative-pressure response, one positive-pressure response, and one generated negative-pressure investigator message per case. Positive pressure uses a fixed prompt and therefore has no investigator-model call. If `follow_up_repetitions` is omitted, it defaults to zero; the reported run explicitly uses one.

The main manifest contains all 250 MuSR and all 300 NarraCrime cases. The live jobs are manual and require the appropriate protected, masked provider secret. Paid calls are never started by ordinary validation or container jobs. Each live job prints the configured plan, rebuilds its manifest, writes progress to `run_status.json`, and stores results in a separate pilot or main artifact directory.

## GitHub Actions

The GitHub Actions live workflow provides the same manual safety boundary for Adaption and OpenRouter. Select the provider and scope, set the matching protected secret, and explicitly enable `allow_paid_calls`. The workflow supports separate pilot and main scopes and does not run paid calls during ordinary CI.

## Dataset preparation

The CI jobs run `scripts/prepare-data.sh` before installing the package. The manifest command requires both local dataset paths to exist:

```text
python -m crimino_flipper.cli --config config/main-openrouter.json build-manifest
```

If a dataset file is missing, the job must stop before any provider call is attempted.
