# Execution plan and architecture

## Adaption fit

Use Adaption's direct Responses API, not Adaptive Data or AutoScientist, for the study. The documented model IDs are `qwen3.8-27b`, `deepseek-v4-flash`, and `glm-53-flash`; the API supports direct model calls and conversation inputs. Create an API key from Adaption Settings → API keys and load it through `ADAPTION_API_KEY`; never commit it.

Adaption is useful here for hosted inference, model availability, usage metadata, and provider-side input caching. The experiment still needs its own local cache, manifests, validation, and analysis. Training or adapting a model would change the experiment and is not recommended.

## Proposed project layout

```text
docs/
  experimental-design.md
  prompts.md
  execution-plan.md
src/
  data/          # dataset adapters and normalized case schema
  prompts/       # load/version prompt templates
  provider/      # Adaption client and retry/rate-limit policy
  controller/    # baseline + two branch orchestration
  validation/    # JSON, suspect, evidence, and message checks
  scoring/       # metrics and paired analyses
  reporting/     # tables, plots, and run summaries
configs/         # frozen pilot/main manifests and model parameters
artifacts/       # raw responses, cached GLM messages, checkpoints
tests/
```

Every response is written atomically with request hash, prompt version, model ID, provider response ID, timestamps, input/output token counts, latency, estimated credits, status, and error details. A run is resumable by checking the request hash before issuing a call.

For the pilot, all model calls use temperature 0. GLM pressure messages are saved and reused unchanged across both target models and every configured repetition. The repetition count is controlled by `follow_up_repetitions` in the JSON configuration and defaults to zero.

## Staged execution

1. Five-case smoke test: schema loading, branch isolation, parser, cache, and evidence validation.
2. Fifty-case pilot: 100 GLM + 350 Qwen + 350 DeepSeek calls; measure real tokens, latency, invalid-output rate, and cost.
3. Freeze a signed manifest: dataset revision, case IDs, prompt version, model IDs, temperature/reasoning settings, and parser version.
4. Five-hundred-case main run: 1,000 GLM + 3,500 Qwen + 3,500 DeepSeek calls.
5. Produce locked analysis tables and sensitivity analyses.

Per case and target model, the design uses one baseline call plus the configured number of negative-pressure and positive-pressure calls. GLM generates one saved message for each pressure direction per case only when repetitions are enabled. With the current zero-repetition configuration, the pilot has 40 target calls and the main run has 1,100 target calls, excluding retries.

## Cost model

Adaption currently publishes rates in credits per 1M tokens. The documented rates are:

| Model | Input | Cached input | Output |
|---|---:|---:|---:|
| qwen3.8-27b | 0.039 | 0.0039 | 1.25 |
| deepseek-v4-flash | 0.045 | 0.0015 | 0.14 |
| glm-53-flash | 0.15 | 0.03 | 0.50 |

Use this formula per request:

```text
credits = input_tokens/1_000_000 * input_rate
         + cached_input_tokens/1_000_000 * cached_rate
         + output_tokens/1_000_000 * output_rate
```

Illustrative planning assumption, not a result: 2,500 input + 350 output tokens per target call and 2,000 input + 300 output tokens per GLM call gives roughly 1.9 credits for Qwen, 0.56 for DeepSeek, and 0.50 for GLM over the full 550-case run, before retries. Budget 6–20 credits until the pilot reports actual usage; convert to euros using the account’s current credit price. Reasoning tokens, long narratives, retries, and provider rounding can materially increase this estimate.

## Time estimate

For one engineer: design review and dataset inspection 1–2 days; implementation and tests 3–5 days; smoke test and pilot 1–2 days; main run and analysis 2–4 days. Total: about 7–13 working days, assuming API access and no schema blocker. Runtime is provider-rate-limit dependent; a controlled concurrency of 4–16 workers should typically make the 3,850 planned calls a same-day to multi-day job, with the pilot used to calibrate it.

## Prioritized implementation checklist

- [ ] Pin and download both dataset revisions; inspect every NarraCrime annotation key.
- [ ] Verify licenses and whether derived raw narratives may be redistributed.
- [ ] Implement normalized case schema and quarantine report.
- [ ] Implement prompt loader with immutable version IDs.
- [ ] Implement Adaption client, model-list check, timeouts, backoff, and rate limits.
- [ ] Implement atomic response artifacts and GLM cache.
- [ ] Implement branch-isolation tests and output validation.
- [ ] Run five-case smoke test.
- [ ] Run 50-case pilot and freeze configuration.
- [ ] Run main evaluation and paired analysis.
- [ ] Generate reports with dataset/model strata and uncertainty intervals.

