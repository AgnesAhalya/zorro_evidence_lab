# Docker and GitLab

## Local Docker workflow

Build and show the pilot plan:

```text
docker compose run --rm plan
```

Run the complete local simulation:

```text
docker compose run --rm simulate
```

Run the test suite:

```text
docker compose run --rm test
```

Simulation artifacts are mounted to `pilot/artifacts/` on the host. Repeated runs reuse matching cached responses.

## Live Adaption workflow

The live service is excluded from ordinary Docker Compose runs. It requires both the `live` profile and an API key:

```text
export ADAPTION_API_KEY='your-key'
docker compose --profile live run --rm adaption-pilot
```

This command makes paid calls. The application still requires the explicit `--allow-paid-calls` argument, which is fixed in the live service definition.

## GitLab pipeline

`.gitlab-ci.yml` validates both configured experiment sizes and contains four stages:

1. `validate`: rebuilds the manifest, runs the simulation twice, confirms caching, and executes the tests.
2. `container`: builds the image and runs plan and test commands inside it.
3. `publish`: on the default branch, publishes commit-tagged and `latest` images to the GitLab Container Registry.
4. `experiment`: exposes separate manual `pilot-live` and `main-live` jobs.

The case counts are read from configuration rather than hardcoded in GitLab YAML:

- `config/pilot.json`: 10 local cases and 20 baseline provider calls.
- `config/pilot-gitlab.json`: 20 GitLab validation cases and 40 baseline provider calls.
- `config/main.json`: all 550 cases and 8,250 provider calls.

The main manifest uses all 250 MuSR and all 300 NarraCrime cases. The two live jobs are manual and require `ADAPTION_API_KEY` to be configured as a protected, masked GitLab CI/CD variable. Paid calls are never started by ordinary validation or container jobs. Each live job prints the configured plan, rebuilds its matching manifest, writes progress to `run_status.json`, and stores artifacts in a separate pilot or main directory.

No Adaption API key is required for CI validation. Live paid calls are intentionally not part of the automatic pipeline.
The container installs the pinned Adaption Python SDK version declared in `pyproject.toml`.

To connect a new GitLab repository:

```text
git init
git add .
git commit -m "Add Zorro evidence pilot"
git branch -M main
git remote add origin <your-gitlab-repository-url>
git push -u origin main
```
