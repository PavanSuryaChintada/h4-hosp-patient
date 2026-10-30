# The demo UI

The React app in `ui/` shows pipeline output to a person. It is never on the scoring path and
holds no detection logic (`docs/phases/09-ui.md` R1): if a number is on screen, it came from the
pipeline, from the standard-check reproduction, or from an evaluation report.

```
python tools/export_ui.py          # pipeline on the training split -> ui/public/data/pipeline.json
cd ui && npm install && npm run dev
```

Re-run the export whenever the pipeline changes. It takes about 25 seconds.

## The data file

`tools/export_ui.py` writes one JSON file, schema version 2, mirrored field for field in
`ui/src/data/contract.ts`. The app fetches it from its own origin at start-up, so it runs with the
network off. Change both files together and bump `SCHEMA_VERSION` in each.

| Block | Source |
|---|---|
| `patients[].medications` | `run_pipeline`: each line as written, generics, method, confidence, abstention |
| `patients[].medsafe` | Every finding in `medsafe.explain.prioritise` order with its confidence-and-limitations text, the actions (collapse first), the collapse graph, and `patient_summary` / `not_checked` word for word. Null for a stage that is not built |
| `workflow` | `medsafe.workflow`: roles, alert permissions, entry permissions, override reasons, the disclaimer |
| `ml_challenger` | The newest `python -m eval.ml_challenger` result |
| `patients[].ehr` | `tools/ehr_reference.py`, the standard-check reproduction |
| `patients[].compare` | The header strip on the patient screen, counted in Python |
| `demo` | Pinned patients and the four `/why` cards, by the criteria below |
| `ehr_reference.score` | The reproduction scored by the organisers' `evaluate.py` on the holdout split |
| `evaluation` | The newest `eval/reports/*.json` with `splits`, copied unchanged |

A stage that is not built exports as null and the UI says "not built yet", never "no issue
found". The converter calls the clinician layer (`prioritise`, `collapse`, `alert_limitations`,
`patient_summary`, `not_checked`) rather than restating any of it, as `docs/engine-handoff.md`
asks.

## The ward

`python tools/serve_ui.py` serves the built app and a small local API on
`http://127.0.0.1:8765`. It is the only place a hand-entered patient is checked, and it checks them
with the shipped code: the record is written as a one-row patients CSV, read by the same adapter
`run.py` uses, run through `run_pipeline`, and shaped by `patient_view`, so a ward patient and an
exported one are the same object on screen.

| Role | Enters (`ENTRIES`) | May do with an alert (`PERMISSIONS`) |
|---|---|---|
| Ward nurse | admission details, the medication list as written | escalate |
| Lab technician | eGFR | nothing; sees alerts only |
| Clinical pharmacist | the generic behind a line the resolver would not guess | accept, override, defer, escalate |
| Consultant physician | nothing | accept, override, defer |

Both tables live in `src/medsafe/workflow.py` and the server enforces them (`check_entry`,
`check`); the UI hides what a role cannot do, but a request it should not send is refused with a
403 regardless. An override needs a reason from `OVERRIDE_REASONS`, and "other" needs a note.

- **A confirmed name** is sent to the pipeline as the generic the pharmacist chose (a "stopped"
  marker on the original line is kept) and shown as written, tagged "confirmed by pharmacist".
- **eGFR** is the lab's entry, never the nurse's: a new record has none, so its renal rules have
  not run, and the trust panel says so until the lab adds it.
- **The pharmacist queue** holds records with a line to confirm, an alert deferred or escalated,
  or an open review request.
- **The audit log** (`data/ward/audit.jsonl`) is append-only: every decision, and every alert
  the first time a prescriber or pharmacist is shown it. Override patterns are computed from it
  by `medsafe.workflow.override_patterns`.
- Records and the log stay in `data/ward/`, under the ignored `/data/`, so hand-entered patients
  never reach the repository. There is no real authentication; the role comes from the demo
  sign-in, as everywhere else in the prototype.

## The trained models

`python -m eval.ml_challenger` trains three models, each in the standard library, each on the dev
split only, and scores each once on holdout through the shipped rule engine and `evaluate.py`:

| Stage | Model | What it replaces in the experiment | Holdout result |
|---|---|---|---|
| 1 | Character n-gram TF-IDF, nearest neighbour | the drug-name resolver | 32 names confidently wrong; rules 0 |
| 2 | Logistic regression over words in and out of negated spans | the condition reader | contraindication recall 0.49; rules 1.00 |
| 3 | Gradient-boosted trees | nothing: it holds back a standard check's alerts | that check's score 0.114 to 0.347, noise 1.17 to 0.05 |

Stage 2 learns from contraindication labels alone (no condition labels exist), which leaves 51
positive examples. Stage 3 cannot predict adverse events or prescriber acceptance, because the
data records neither; it learns which alerts match a real issue that is not minor. Its trees
split most on eGFR and the renal flag: they learned from data the eGFR blindness the rules avoid
by design. None of the three is on the scoring path: nothing in `run.py`, `src/`, `eval/run.py`
or `eval/sweep.py` imports them. Holdout is out of sample for the models only: the rules'
condition vocabulary was built on all training text (D-025) and their synonym list on dev
failures plus general knowledge (D-014), so the rules' perfect holdout rows are optimistic and
are not a forecast for the hidden split. Details and every number: `docs/ml-challenger.md`.

## The standard EHR check

`tools/ehr_reference.py` reproduces what a typical hospital clinical-decision-support (CDS) layer
does with the same list and the same reference tables. A clinician judge will know what these
systems really do, so it is built to be fair, not to lose:

- **Exact formulary names only.** Dose forms, strengths and frequencies are stripped exactly as
  the pack's `baseline/baseline.py` strips them. Misspellings, abbreviations and combination
  brands are "not in formulary" and are left out of every check.
- **Every listed interaction pair**, at the table severity, minor included.
- **Duplicates** among recognised lines: the same generic twice, or two members of one
  duplicate group.
- **One flat renal warning** per recognised drug with renal rules, at the most restrictive tier,
  whatever the eGFR. eGFR is never read.
- **Not reproduced:** drug-disease, allergy and pregnancy checks. Diagnoses and allergies are free
  text here, and a CDS layer needs them coded. Leaving these out lowers the reproduction's alert
  count, so it does not inflate the noise it is shown making.

On the 1,500 training patients it raises 1.69 alerts per patient. That is quiet, but for the
wrong reason: 3,389 of 9,087 lines are not in its formulary. On the holdout split, `evaluate.py`
scores it 0.114, with serious recall 0.23 and 1.17 noise alerts per patient. Most of the noise
is flat renal warnings: 382 renal alerts, 56 of which match a real issue. These numbers are
regenerated on every export.

## Choosing demo patients

The criteria are in the `pick_*` functions in `tools/export_ui.py`, applied to the training
split. Where a criterion is about what is really wrong with a patient, it reads the training
labels: **the labels choose who is shown, and the pipeline decides what is shown**. Each `/why`
card prints its label as the answer key, so a reader can see Medsafe catch or miss it.

| Pin or card | Criterion |
|---|---|
| Interaction cluster (pin) | The most serious labelled interactions sharing one drug, at most 12 lines |
| Same drug, two kidneys (pin, card 3) | One renal drug at the same written strength. One patient is labelled at its most restrictive tier; the other is above every tier with no label |
| Hidden in a combination (pin, card 2) | A labelled same-generic duplicate with one copy inside a combination the standard check cannot open |
| Could not resolve (pin) | The most lines the resolver abstained on (from pipeline output, not labels) |
| Nothing labelled (pin) | No labelled issue, at least 6 medicines, eGFR recorded |
| Brand chaos (card 1) | A labelled same-generic duplicate written in different words, where the standard check recognises at most one line |
| Alert fatigue (card 4) | The loudest standard screen that still misses serious labelled issues |

The brief's own examples (metformin written three ways, Glycomet-GP plus metformin) do not occur
in the training set as current medicines. The cards use the real cases the criteria find, which
are mostly paracetamol and metformin.

## What the UI must not do

`tests/test_ui_copy.py` enforces two rules over every UI source file and the data file:

- the word "safe" never appears;
- no eGFR is compared to a number. A threshold in the browser would be a second renal rule that
  could drift from the pipeline's. The tier ladder on card 3 draws `renal_rules.csv` rows from
  the export, and the tier a patient falls in comes from Medsafe's alert.

Pharmacist-review handoffs are stored in the browser's `localStorage`. The prototype has no
backend. The override-rate figure on card 4 (49% to 96% of alerts overridden) is from van der Sijs
et al., "Overriding of drug safety alerts in computerized physician order entry", *JAMIA* 2006;
13(2):138-147.
