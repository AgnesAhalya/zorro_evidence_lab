# Prompt specification

The canonical runtime prompts are maintained as separate files:

- `prompts/shared_system.txt` — evidence and JSON-output rules for target models.
- `prompts/baseline.txt` — initial case decision and required target-response schema.
- `prompts/investigator.txt` — senior-investigator message and cited-claim schema.
- `prompts/reconsider.txt` — optional neutral reconsideration prompt; not active in the reported negative/positive run.

## Output requirements

All active prompts request exactly one JSON object with double-quoted keys and values, no Markdown fences, and no surrounding commentary. The parser accepts a valid object in a fence or surrounded by incidental text for provider robustness, but the prompt contract remains JSON-only. Target evidence fields are limited to concise sentences. Investigator messages are limited to 120 words and must include one to three short claims copied from the source narrative.

The parser accepts a valid object wrapped in a JSON code fence or surrounded by incidental text, but does not repair malformed JSON or change substantive model output. Empty, incomplete, malformed, or schema-invalid responses are saved and marked invalid rather than terminating the full run.

## Visibility

- Target models receive the original case, candidates, their own saved baseline response, and exactly one pressure message.
- The positive and negative branches always begin from the same saved baseline conversation.
- Target models do not receive the culprit field or hidden annotations.
- The investigator model receives the case, candidates, and the single suspect it must support.
- Saved investigator messages are reused unchanged across both target models and every configured repetition. The repetition count is controlled in JSON and defaults to zero when omitted. The reported main run sets `follow_up_repetitions` to `1`, producing one negative and one positive response per baseline.

## Positive-pressure isolation

Positive pressure is a fixed prompt rendered with the assigned reference culprit. It does not call the investigator model and does not reveal that the assigned suspect is correct. The target must still reconsider the original evidence and report contradictory evidence. The positive branch starts from the same saved baseline context as the negative branch and never receives the negative message or response.
