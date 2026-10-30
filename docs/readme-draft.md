# README sections, drafted for merging

The repository README is being rewritten in the portal workstream. These sections are drafted here so they can be merged without the two edits colliding. Every figure is from the organisers' `evaluate.py` and regenerates with `python -m eval.run`; check docs/evaluation.md for the current values before merging.

---

## How it works

Medsafe is a second pair of eyes on a patient's consolidated medication list: the list a nurse copies from the slips, strips and bottles of up to three prescribers. It resolves every line to its generic, checks four kinds of risk against the reference tables, and puts the result in front of a clinician who decides. It never claims a list is safe; it says what it found in what it saw.

**The workflow (point of care).** Identify the patient, capture the list, resolve every line, read the clinical context and say what is missing, check, prioritise, then let the clinician accept, override with a reason, defer, or escalate to a pharmacist, with every decision recorded. See docs/WORKFLOW.md.

**Batch evaluation mode.** The same engine over every test patient, producing the two submission files:

```
python run.py --split test --out submission
python -m eval.validate_submission submission
```

## Results

| | Training patients (official scorer) |
|---|---|
| **Near-miss recall** | **90 / 90** |
| **Resolution accuracy on misspelled entries** | **99.94%** |
| Serious-issue recall | 1.0000 |
| Precision | 1.0000 |
| Noise alerts per patient | 0.0000 (fatigue multiplier 1.0000) |
| Primary score | 1.0000, against the pack baseline's 0.4071 |

These are training-set figures and partly in-sample: the condition vocabulary and the stopped-medicine markers were fixed by reading the training patients. The hidden test set has phrasings the training set does not (docs/DECISIONS.md D-025).

## Why minor alerts never interrupt

Minor alerts drive alert fatigue; fatigue drives dismissal; dismissal buries the serious alert behind them. So minor issues are shown to the clinician, ranked last, and never submitted as alerts. The scorer penalises them because this is what happens in hospitals; leaving them out measured +0.0518 for a perfect detector, which corroborates the choice rather than motivating it.

## Limitations

- Training scores are in-sample for the rules (see above).
- A line the resolver cannot identify is flagged "verify manually" and not checked.
- Missing eGFR means no renal claim; the alert says so.
- The data says how many prescribers wrote a list, not which wrote which line.
- The reference tables are simplified for this exercise; a clinician decides.
