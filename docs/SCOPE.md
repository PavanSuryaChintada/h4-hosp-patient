# Scope

Every feature maps to one of the pack's five expected outcomes. A feature that maps to none is not built.

| Outcome | What the pack asks |
|---|---|
| O1 | A prioritised alert list per patient: issue type, severity, drugs involved, a concrete suggested action |
| O2 | Alert fatigue is scored: serious recall up, low-value volume down, both shown |
| O3 | A fuzzy brand/generic resolution module with reported match accuracy on misspelled inputs |
| O4 | Confidence and limitations with every alert, a mandatory "a clinician decides", never "safe" |
| O5 | Recall on the seeded near-misses, reported prominently |

## Built

| Feature | Where | Serves |
|---|---|---|
| Name resolution: exact, synonym, combination, prefix, fuzzy, abstain | `src/medsafe/resolve/` | O3 |
| Resolution accuracy on misspelled entries, from the official scorer | `python -m eval.run`, docs/evaluation.md | O3, O5 |
| Four rule families, table severity and action verbatim | `src/medsafe/rules/` | O1 |
| Regimen (stopped and non-medicine lines excluded), condition matching with negation | `src/medsafe/rules/` | O1 |
| Minor alerts shown, never submitted | `src/medsafe/output/policy.py` | O2 |
| Noise per patient, fatigue multiplier, floor and ceiling | `python -m eval.floor`, `python -m eval.run` | O2 |
| Confidence-and-limitations text on every alert; no-issue statement | `src/medsafe/explain/limitations.py` | O4 |
| Data-quality notes for unreadable values | `src/medsafe/explain/data_quality.py` | O4 |
| Prioritise, and collapse serious interactions into the drug to review first | `src/medsafe/explain/prioritise.py` | O1, O2 |
| Act (accept, override with reason, defer), escalate, append-only audit, override patterns | `src/medsafe/workflow.py`, portal | O4 (a clinician decides; the human-in-the-loop path the pack requires) |
| Near-miss recall, named misses | `python -m eval.run` | O5 |
| `prescriber_count` in the queue | portal | O1 (the three-doctor silo the scenario describes) |
| Submission validated with the official validators | `python -m eval.validate_submission` | all (an unreadable file scores zero) |

## Not built

| Feature | Why not |
|---|---|
| ABHA / ABDM integration, a fetch layer, a mock network call, a consent flow | The pack gives us the consolidated list; our scope starts where it lands. The intake screen explains the two routes in one static panel (S2) |
| Real authentication | Roles are chosen at sign-in; the role only decides what can be actioned |
| Writing changes back to a prescription | The system recommends; a clinician decides. Nothing is applied automatically |
| Context re-scoring of severity in the submission | It lowers the score: the labels use table severity (D-015). Context is shown to the clinician as notes |
| An LLM at runtime, or on test text | Reproducibility, offline running, and the pack's rule against labelling test patients (D-024). The resolution fallback is off by measurement (D-023) |
| Which prescriber wrote which line | Not in the data; only the count is. The portal shows the count, never an invented attribution |
