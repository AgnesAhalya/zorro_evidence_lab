# Execution plan and architecture

## Purpose

The project runs a paired investigation workflow: each target model produces a baseline suspect identification, then receives an isolated negative-pressure branch and an isolated positive-pressure branch. The original narrative and baseline context are unchanged across branches.

The reported main configuration uses OpenRouter with:

- Target models: `qwen/qwen3.7-flash` and `z-ai/glm-5.3-flash`.
- Investigator model: `openai/gpt-oss-20b` for negative-pressure messages.
- Temperature: `0` for all calls.
- Follow-up repetitions: `1` in the reported run; omitted configuration defaults to `0`.
- Positive pressure: fixed prompt, so it does not require an investigator-model call.

Adaption configurations remain available separately. Their provider, models, pricing, timeout, and output limits are read from the relevant JSON configuration and are not hardcoded in the controller.

## Call plan

For each case and target model, the controller makes one baseline call and one call for each enabled pressure condition per configured repetition. A negative-pressure investigator message is generated once per case and reused across target models and repetitions. Positive pressure uses a fixed local prompt.

| Run | Cases | Baseline | Negative | Positive | Investigator | Total before retries |
|---|---:|---:|---:|---:|---:|---:|
| Local pilot | 10 | 20 | 20 | 20 | 10 | **70** |
| Main experiment | 550 | 1,100 | 1,100 | 1,100 | 550 | **3,850** |

The 20-case GitLab validation configuration follows the same one-repetition design and plans 140 provider calls. Counts are generated from configuration by the CLI and workflow; they are not manually duplicated in CI files.

## Configuration and reproducibility

The case count, dataset split, model list, pressure conditions, repetition count, output-token allowance, timeout, retry policy, and pricing are stored in JSON configuration files. Before a live run:

1. Prepare the pinned local datasets.
2. Build the public and private manifests.
3. Confirm model IDs, prompt versions, temperature, repetition count, and output limit.
4. Run compilation, tests, Docker plan, Docker tests, and local simulation.
5. Confirm the provider key is supplied only through the environment or protected CI secret.

Changing the case count, model list, prompt text, pressure implementation, parser, or repetition count requires a new manifest and run identifier. Artifacts from different configurations must not be mixed.

## Runtime architecture

```text
data_loaders.py  ->  manifest.py  ->  prompts.py
                                      |
                                      v
                              controller.py
                              /     |      \\
                         baseline  negative  positive
                                      |       |
                             investigator  fixed prompt
                                      \\     /
                                       storage.py
                                           |
                                      scoring.py
                                           |
                                     reporting.py
```

Every response is stored atomically with the request hash, prompt version, model ID, provider response ID when available, timestamps, token usage, latency, estimated cost, validation status, and error details. Cached responses are reused only when the request hash matches exactly.

## Validation, retries, and missingness

The parser accepts valid JSON in a Markdown fence or surrounded by incidental text, but it does not repair malformed JSON. Empty, incomplete, malformed, schema-invalid, timed-out, or provider-error responses are saved and marked invalid.

The provider retries retryable rate-limit and server failures according to the configured policy. Invalid or null responses are retried up to the configured validation retry count, with the configured wait between attempts. Exhausted failures remain invalid in the run summary. An invalid baseline skips dependent pressure tasks for that case/model; an invalid negative investigator message skips only the negative branch. The positive branch remains independent.

## Analysis outputs

The analysis reports overall and model-wise baseline accuracy, accuracy-conditioned flips, accuracy-unconditioned answer changes, incorrect-to-correct recovery, confidence changes, investigator-preference alignment, directional accuracy transitions, invalidity, missingness, and case coverage. Results are also stratified by dataset and NarraCrime difficulty where valid data permit.

With one repetition, majority-case analysis is equivalent to the single pressure response. If repetitions are increased, the report additionally includes replicate-level and majority-case results while preserving the case/model paired structure.

## Provider safety

Simulation, tests, Docker validation, and manifest construction do not make paid calls. Live execution requires both the provider key and the explicit `--allow-paid-calls` flag. The API key is never committed, written to artifacts, or printed in logs.
