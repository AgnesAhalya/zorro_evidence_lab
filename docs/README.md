# Experiment documentation

This documentation describes the completed EpistemicBalance evaluation workflow and its reproducible execution path.

## Read in this order

1. [`experimental-design.md`](experimental-design.md) - research questions, paired conditions, datasets, metrics, limitations, and branch isolation.
2. [`prompts.md`](prompts.md) - prompt contracts, visibility rules, JSON schemas, and positive/negative isolation.
3. [`execution-plan.md`](execution-plan.md) - call plan, configuration, retries, validation, storage, and analysis outputs.
4. [`docker-gitlab.md`](docker-gitlab.md) - offline verification and manual live-run procedures.

The main study uses 550 cases, two target models, one baseline response, one negative-pressure response, and one positive-pressure response per target model and case. The 10-case pilot is a feasibility check. All repetition counts are configuration-driven, and omitted repetition settings default to zero.

Tests, Docker plan/test/simulation jobs, and manifest construction do not make paid provider calls. Live execution requires an explicit `--allow-paid-calls` flag and a protected provider key.
