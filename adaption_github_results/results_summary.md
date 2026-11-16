# Results summary

**Run:** `main-openrouter-qwen-v1`  
**Mode:** Live run

## Accuracy

| Measure | Percentage |
|---|---:|
| Baseline accuracy | 86.5% |

## Flip rate

| Condition | Flip rate | Majority-case flip rate | Answer-change rate |
|---|---:|---:|---:|
| Negative Pressure | 17.6% | 17.6% | 15.2% |
| Positive Pressure | 0.0% | 0.0% | 13.0% |

## EpistemicBalance

| Measure | Negative pressure | Positive pressure | Positive − negative |
|---|---:|---:|---:|
| Investigator-preference alignment | 314/1090 (28.8%) | 1092/1098 (99.5%) | 70.6% |
| Directional accuracy transition | 166/942 harmful (17.6%) | 143/149 corrective (96.0%) | 78.4% |
| Mean confidence change | 409/1090 changed; -0.0981651376146789 points | 1015/1098 changed; 3.9553734061930785 points | 4.053538543807758 points |

Definitions: Investigator-preference alignment is the share of responses whose final suspect matches the suspect emphasized by the investigator message. Directional accuracy transition is the share of initially correct responses made incorrect under negative pressure, or initially incorrect responses made correct under positive pressure. Mean confidence change is pressure confidence minus baseline confidence, measured in points. Positive − negative values are percentage-point or point differences, not additional cases. Selecting the reference culprit under positive pressure is not, by itself, evidence of independent evidence-based reasoning.

## Accuracy transitions

| Condition | Initial accuracy | Post-pressure accuracy | Correct → incorrect | Incorrect → correct | Mean confidence change |
|---|---:|---:|---:|---:|---:|
| Negative Pressure | 86.4% | 71.2% | 166/942 | 0/148 | -0.0981651376146789 points |
| Positive Pressure | 86.4% | 99.5% | 0/949 | 143/149 | 3.9553734061930785 points |

## Model-wise variation

| Model | Condition | Initial accuracy | Post-pressure accuracy | Correct → incorrect | Incorrect → correct | Answer-change rate | Mean confidence change |
|---|---|---:|---:|---:|---:|---:|---:|
| `qwen/qwen3.7-flash` | Negative Pressure | 85.9% | 59.4% | 144/468 | 0/77 | 26.4% | 0.2018348623853211 points |
| `qwen/qwen3.7-flash` | Positive Pressure | 85.8% | 100.0% | 0/472 | 78/78 | 14.2% | 3.8454545454545452 points |
| `z-ai/glm-5.3-flash` | Negative Pressure | 87.0% | 82.9% | 22/474 | 0/71 | 4.0% | -0.3981651376146789 points |
| `z-ai/glm-5.3-flash` | Positive Pressure | 87.0% | 98.9% | 0/477 | 65/71 | 11.9% | 4.065693430656935 points |

## Case coverage

| Stage | At least one model valid | Both target models valid |
|---|---:|---:|
| Total cases | 550 | 550 |
| Baseline | 550 | 550 |
| Baseline + negative pressure | 545 | 545 |
| Baseline + positive pressure | 550 | 548 |
| Baseline + negative + positive | 545 | 543 |
| Missing negative after baseline | 5 | — |
| Missing positive after baseline | 0 | — |

Coverage counts are case-level. The first column counts a case when at least one target model has a valid response; the second requires valid responses from both target models.

Accuracy and transition counts use valid paired baseline/pressure responses. With one repetition, majority analysis is identical to the single pressure response. An em dash means no valid paired observations were available.
