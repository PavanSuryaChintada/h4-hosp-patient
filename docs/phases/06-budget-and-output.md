# Phase 6 — Alert Budget & Output Contract

> **Amended (docs/DECISIONS.md D-015, D-018).** The real output is the pack's two files (`H4_predictions.csv`, six columns; `H4_resolution.csv`). There is **no per-patient cap**: noise counts only false alerts and alerts on minor issues, so capping a true alert loses recall and saves nothing. Minor alerts are left out by one measured constant, `EMIT_MINOR = False`. Severity is the table's, unchanged.

**Time:** 2h. **If the output does not parse, the score is zero regardless of the detector.**

---

## Part A — the alert budget

**R1 — Rank, then cap.** Ranking score:

```
priority = severity_weight × resolution_confidence × actionability
severity_weight: high 1.0 · medium 0.5 · low 0.15 · info 0.05
actionability:   a concrete drug change 1.0 · "confirm intended" 0.7 · informational 0.3
```

**R2 — Cap per patient.** Default 5. **Make it a single named constant and tune it in Phase 7 against the real penalty curve.** If `evaluate.py` penalises per low-severity alert, the optimum may be 3.

**R3 — Never cap out a `high`.** If a patient has 7 high-severity findings, all 7 ship. The cap trims the tail, not the head. Document this.

**R4 — Report what was capped.** `alerts_suppressed: n` on the patient record. The brief's whole theme is alert fatigue, so showing you counted what you held back is the point, not a footnote.

**R5 — A patient with no findings gets an explicit record**, not an empty one: `"No issue found in the N medications listed."` plus the limitations line. Never the word "safe".

---

## Part B — the output contract

**R6 — Build a writer module and a validator.** `src/medsafe/output/writer.py` and `validator.py`. When the real format is confirmed, you change the writer only.

**R7 — Assumed format until confirmed** — one row per alert:

```
patient_id, alert_rank, issue_type, rule_id, severity,
drugs_involved, suggested_action, confidence, reasons, limitations
```

**R8 — Validate your own output before it ships.** `validator.py` checks: every patient present, no nulls in required fields, severity values in the allowed set, rank contiguous from 1, no duplicate `(patient_id, rule_id, drugs)` rows. `run.py` fails loudly if validation fails. **Shipping output you have not parsed back is how teams score zero with working code.**

**R9 — One entry point.**

```
python run.py --input data/ --output submission.csv
```

Prints: patients processed, alerts emitted, alerts suppressed, runtime, and the validation result.

---

## Deliverables

- [ ] `src/medsafe/budget/rank.py` + the cap constant in one place
- [ ] `src/medsafe/output/writer.py`
- [ ] `src/medsafe/output/validator.py`
- [ ] `run.py`
- [ ] `tests/test_output.py` — round-trip write then validate, plus each failure mode

## Acceptance

- `python run.py` on fixtures produces a file that passes its own validator.
- A patient with 7 high findings emits all 7 despite a cap of 5.
- A patient with no findings emits the explicit no-issue record.
- Corrupting one output field makes the validator fail with a specific message.

## Claude Code prompt

```
Build Phase 6 per 06-budget-and-output.md, on top of Phase 5.

1. rank.py: priority = severity_weight x resolution_confidence x actionability, with the
   weights in the spec as named constants. ALERT_CAP in one place with a comment that it is
   tuned in Phase 7.
2. High-severity findings are never capped out. The cap trims the tail only. Test it.
3. Record alerts_suppressed per patient.
4. A patient with zero findings emits an explicit record saying no issue was found in the N
   medications listed, plus the limitations line. The word "safe" must not appear - add a test
   that greps the output for it and fails.
5. output/writer.py emitting the assumed CSV schema in the spec, with the column list in one
   constant so it can be changed in one edit.
6. output/validator.py checking: all patients present, no nulls in required fields, severity in
   the allowed set, rank contiguous from 1, no duplicate (patient_id, rule_id, drugs).
7. run.py as the single entry point with --input and --output, printing patients processed,
   alerts emitted, alerts suppressed, runtime and the validation result. Exit non-zero if
   validation fails.
8. tests/test_output.py: write then validate round-trip, and one test per validator failure mode.

Docstrings on every public function.
```
