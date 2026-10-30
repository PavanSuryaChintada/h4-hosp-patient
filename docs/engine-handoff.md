# Engine handoff, for the portal (ui/)

From the engine side to whoever builds `ui/` and `tools/export_ui.py`. Phase 3 has landed: every `PatientResult` now carries findings and alerts, so the exporter's `medsafe_view()` seam will raise `NotImplementedError` until its converter is written. Everything below is computed in Python; the portal should not compute any of it.

## What `run_pipeline(dataset)` returns per patient (`PatientResult`)

| Field | What it holds |
|---|---|
| `patient` | `Patient`: age, sex, weight_kg, egfr, pregnant (None = not applicable or unknown), diagnoses, allergies, medications, `prescriber_count`, `unreadable_fields` |
| `notes` | Data-quality notes for unreadable values |
| `resolutions` | One `Resolution` per line: `raw`, `generics` (tuple), `method` (exact, synonym, parts, prefix, fuzzy, non_drug, abstained), `confidence`, `candidates`, `abstain_reason`, `verify_manually` |
| `findings` | Every `Finding`, minor included: `issue_type`, `drugs`, `severity` (table, verbatim), `action` (table, verbatim; a fixed template for pregnancy letters), `rule_id`, `evidence` (dict of the triggering values), `raw_drugs`, `confidence` |
| `alerts` | The predictions-file rows (no minor): the six submission columns plus `confidence_and_limitations` |
| `rules.regimen.entries` | Each line's `status`: active, stopped, not_a_medicine, unresolved |
| `rules.conditions` | `present`, `negated` (condition ids) and `evidence` (the clause behind each) |

## Functions to call, not reimplement

| Need | Call |
|---|---|
| The line at the top of a patient: "No issue was found in the N medicines listed..." or the alert count, with what was not checked | `medsafe.explain.limitations.patient_summary(patient, rules.regimen, len(alerts))` |
| What could not be checked for this patient, one sentence each | `medsafe.explain.limitations.not_checked(patient, rules.regimen)` |
| The limitations text for a finding (minor ones too) | `medsafe.explain.limitations.alert_limitations(finding, patient, rules.regimen)` |
| Order alerts for display | `medsafe.explain.prioritise.prioritise(findings)` |
| The drug(s) to review first | `medsafe.explain.prioritise.collapse(findings)`: `Collapse(drugs, cleared, remaining, total, summary)`, or None when no drug clears more than one serious interaction |
| Roles, permissions, override reasons | `medsafe.workflow.ROLES`, `PERMISSIONS`, `OVERRIDE_REASONS` (export them; do not hardcode) |
| Validate an audit event before appending it | `medsafe.workflow.check(AuditEvent(...))` |
| Override patterns from an audit log | `medsafe.workflow.override_patterns(events)` |
| The disclaimer, word for word | `medsafe.explain.limitations.DISCLAIMER` |

## Results screen (P9)

Read, never retype, from the newest `eval/reports/*.json` (`python -m eval.run`):

- near-miss recall: `splits.<split>.official.components.near_miss_serious_recall`, and the caught/total count from `splits.<split>.near_misses[].caught`
- resolution accuracy on misspelled entries: `splits.<split>.official.resolution_accuracy_misspelled`
- serious recall, precision, graded recall, noise per patient, fatigue multiplier: `splits.<split>.official.components`
- per-rule fidelity: `splits.<split>.rules`

## Policy points to respect

- **Defer.** Your spec gives defer to no role explicitly. `PERMISSIONS` gives it to prescriber and pharmacist (the roles that can accept). Change it there if that is wrong.
- **Prescriber attribution.** The data records `prescriber_count`, not which prescriber wrote which line. Show the count and a marker for three; do not show which alert "crosses prescribers", because that would be invented.
- **Minor alerts** are real issues: show them, ranked last, never as interruptions. When explaining why, lead with the clinical reason (fatigue, then dismissal, then the buried serious alert), not the scorer.
- **"Safe"** never appears about a patient. `tests/test_ui_copy.py` (yours) checks UI strings; `tests/test_compliance.py` (mine) checks the pipeline's output.
