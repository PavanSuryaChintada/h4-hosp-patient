# Phase 4 — Patient-Context Notes (UI layer only)

**Rewritten** after the data pack arrived (docs/DECISIONS.md D-015). The original Phase 4 re-scored each finding's severity by eGFR, age, drug count and confidence. **That would lower the score**, so it never touches the submission.

---

## Why the rewrite

`tools/verify_label_severity.py` recomputes every training label's severity from the reference tables: **3,241 of 3,241 match the table exactly** (interaction 1,834, renal 698, duplicate 507, contraindication 202). The labels are never re-scored by patient context, and `graded_recall` (weight 0.15) only credits an alert carrying the exact severity. Re-scoring would move correct severities to wrong ones.

So:

- **The submission carries table severity, unchanged.** Interactions from `interactions.csv`; renal from the most restrictive `renal_rules.csv` tier the eGFR is below; duplicates from `duplicate_therapy_groups.csv` (no group: moderate; paracetamol: major); contraindications from `drug_disease_contraindications.csv` (at most one per drug, most severe), plus pregnancy letter X → contraindicated and D → major.
- **Patient context becomes explanation.** The UI shows, beside each alert, why this patient's situation makes it more or less pressing: *"eGFR 28 is well below the 45 threshold"*, *"age 79 on an anticoagulant"*. A prescriber reads it; the predictions file never sees it.

---

## Requirements

**R1 — Notes, never severities.** `src/medsafe/explain/context.py` returns context notes for a finding. It has no severity field and cannot change one.

**R2 — Policy as data.** A `CONTEXT_RULES` table of `(name, predicate, note_template)` covering: eGFR far below a threshold (< 0.6 × threshold), age ≥ 75 on a sedative, anticoagulant or hypoglycaemic, drug count ≥ 8, a resolution the resolver was unsure of.

**R3 — BLOCKING: unknown never means safe.** With age unknown, the age rule does not fire **and** the result names `age` in `unverifiable`, exactly as eGFR does when eGFR is unknown. Silently skipping the rule would treat unknown age as "not elderly". `tests/test_phase4_contract.py` enforces this and runs as soon as `medsafe/explain/context.py` exists; this phase cannot land without it passing.

---

## Deliverables

- [ ] `src/medsafe/explain/context.py`: `context_notes(finding, patient, drugs) -> ContextNotes` with `notes: tuple[str, ...]` and `unverifiable: tuple[str, ...]`
- [ ] `tests/test_phase4_contract.py` passing (already written)
- [ ] UI: the notes beside each alert, labelled as context, below the table action

## Claude Code prompt

```
Build Phase 4 per docs/phases/04-context-severity.md (the rewritten, UI-only version).

1. src/medsafe/explain/context.py: context_notes(finding, patient, drugs) returning
   ContextNotes(notes, unverifiable). No severity field anywhere. Rules as a CONTEXT_RULES table.
2. Missing age, eGFR or pregnancy status: the rule that needs it does not fire, and the field is
   named in unverifiable. Never treat unknown as safe.
3. Make tests/test_phase4_contract.py pass. Nothing in this phase may change what goes into
   H4_predictions.csv.

Docstrings on every public function.
```
