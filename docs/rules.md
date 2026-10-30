# Rules

Every alert comes from one of four rule families, each a pure function in `src/medsafe/rules/`, run over the patient's current regimen. Severity and suggested action are copied from the reference tables word for word (docs/DECISIONS.md D-015). On all 1,500 training patients the four families reproduce every label exactly: 3,241 of 3,241, none missed, none false, none at the wrong severity (`tests/test_rules.py`).

## The regimen comes first

`rules/regimen.py`. Resolution is not the regimen: the resolution file names every line, but the rules see only lines that are current medicines.

| Line | Status | Checked by the rules |
|---|---|---|
| a medicine | `active` | yes; a combination brand contributes each of its generics, remembering which entry it came from |
| marked stopped, discontinued, withdrawn, held, omitted, or "not taking" | `stopped` | no (it still resolves to its generic) |
| "Physiotherapy", "BP charting" | `not_a_medicine` | no |
| the resolver abstained | `unresolved` | cannot be; flagged for manual check |

"(old Rx)" alone is not stopped: an old prescription still on the list is still being taken.

## Rule ids

| Rule id | Family | Fires when | Severity | Action |
|---|---|---|---|---|
| `INTERACTION:a+b` | interaction | two different generics in the regimen form a pair listed in `interactions.csv` (components of one combination count) | the pair's | the pair's |
| `DUPLICATE_SAME:g` | duplicate_therapy | generic `g` appears in two or more entries (a combination plus a single brand, a brand plus its generic name, the same line twice) | `g`'s group severity; no group: moderate; paracetamol: always major | the group's |
| `DUPLICATE_GROUP:group:a+b` | duplicate_therapy | two different generics of one `duplicate_therapy_groups.csv` group sit in different entries; components of one combination never count against each other | the group's | the group's |
| `RENAL:g<threshold` | renal_dose | eGFR is recorded and strictly below a tier of `renal_rules.csv` for `g`; the lowest such threshold wins. No eGFR, no renal alert; "CKD" text is never read | the tier's | the tier's |
| `CONTRAINDICATION:g:why` | contraindication | `g` meets a row of `drug_disease_contraindications.csv` for a condition in the diagnosis text, an allergy in the allergy text, or pregnancy (pregnant = Y); when pregnant, letter X is contraindicated and D major. At most one per drug, at its most severe level; `why` names the winning condition or letter | the most severe applicable | that row's |

## Conditions from free text

`rules/conditions.py` and the reviewed vocabulary in `rules/condition_terms.py`. Only the 15 condition ids the contraindication table uses are recognised (12 diagnoses, 3 allergies); pregnancy comes from the pregnancy field. Text splits into clauses on `;`, `,`, brackets and ` - `; a clause with a negation cue ("no", "not", "ruled out", "denies", "tolerated", "normal", ...) negates the conditions named in it and nowhere else. Words match the vocabulary exactly, or with one typo (5 to 7 letters) or two (8 or more); abbreviations ("PUD", "BA", "PD", "DCMP") match exactly. A blank diagnosis yields nothing, and nothing is inferred from the medication list.

Measured against conditions back-derived from the labels (`python tools/derive_condition_truth.py`): 83 of 83 proven present found, 0 of 3,418 proven absent fired.

## What is submitted

`output/policy.py`: every finding becomes a row of `H4_predictions.csv` except minor ones (`EMIT_MINOR = False`, D-018). Minor alerts drive alert fatigue, fatigue drives dismissal, and dismissal buries the serious alert; the clinician view still shows them, ranked last. Each row carries the table's severity and action, a confidence (the resolution confidence of the least certain line behind it), and the confidence-and-limitations text: the rule that fired, what could not be checked for this patient, that the list may be incomplete, and that a clinician decides.
