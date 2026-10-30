# Decisions

Deliberate departures from `docs/phases/`, and choices the phase docs left open. Each entry says what the spec said, what we do instead, and why.

---

## D-001 Keep the patient: a bad value degrades one field, never the record

**Spec** (Phase 1, R3): a malformed row is skipped.

**We do:** a clinical value that fails validation (wrong type, out of range) loads as `None` and the patient is kept. The field is named in `Patient.unreadable_fields` and recorded in the load report as `{patient_id, field, raw_value, reason}`. Only two cases drop a patient:

- no patient id, or one already loaded from an earlier row
- a missing or empty medication list

A CSV row of the wrong width is kept and flagged as malformed, because its patient id and medications may still be good.

**Why:** scoring is recall-based. A dropped patient is a guaranteed miss on every issue they have, and it shows up nowhere except the recall number. One unparseable weight must not cost a patient their interaction checks.

**Consequences**

- `LoadReport` counts `loaded_clean`, `loaded_degraded` and `skipped` separately, with a per-field breakdown. `run.py` prints it.
- The output carries one note per unreadable field, for example *"eGFR could not be read; renal checks not verifiable for this patient."* (`src/medsafe/explain/data_quality.py`). Same principle as an abstained medication name: never silently incomplete.
- `tests/test_pipeline.py`: a patient with an unparseable weight still loads, runs through the pipeline, and appears in the output with the degradation noted.
- **Open:** drug and interaction rows are still skipped whole when malformed. A skipped drug row silently costs every patient on that drug. Revisit when the real reference tables arrive.

---

## D-002 Unknown never means safe, including a degraded value

A degraded value is `None`, exactly like a value the source never recorded. D-001 therefore adds no new path downstream: whatever Phases 3 and 4 do with `None` applies. Checked against those specs:

| Field | Used by | Holds? |
|---|---|---|
| eGFR | Phase 3 renal: `None` emits an unverifiable finding. Phase 4: base level kept, flagged `unverifiable` | Yes |
| Age | Phase 4: age ≥ 75 on a sedative, anticoagulant or hypoglycaemic is +1 | **Gap.** With `None` the modulator cannot fire, so unknown age is silently treated as "not elderly". Phase 4 must flag the finding unverifiable for age and say so in `severity_reasons`. Whether to also apply the +1 conservatively is a Phase 4 decision |
| Weight | No check in Phases 3 to 6 reads it | Nothing to treat as safe. The note still says weight-based checks are not verifiable, which stays true if one is added |
| Pregnancy | Phase 3 contraindication, Phase 4 pregnancy floor | Phase 3 must flag pregnancy checks unverifiable when status is `None` and the patient is on a category D or X drug |

These are obligations on Phases 3 and 4, each with a test there.

---

## D-003 `Patient` gains `unreadable_fields`

Phase 1 froze the `Patient` dataclass. We added one field, defaulting to `()`, so a downstream stage can tell "could not be read" from "not recorded" without the load report in hand. Every existing constructor still works.

---

## D-004 Stdlib `csv` and `json` only; pandas dropped

**Spec** (00-MASTER §4): stdlib plus pandas for IO.

**We do:** the adapter reads with `csv` and `json`. `requirements.txt` is `rapidfuzz` and `pytest` only.

**Why:** pandas coerces blank cells to `NaN`, which is exactly the missing-as-a-value bug Phase 1 R4 warns about, and it would need undoing on every read. It is also the largest dependency we had. Fewer dependencies is fewer ways the grader's run fails.

The organisers' `evaluate.py` does need pandas and numpy, so they live in `requirements-dev.txt`, used only by the evaluation harness (D-014). The pipeline still runs on the standard library plus `rapidfuzz`.

---

## D-005 `.gitignore` anchors `/data/`, not `data/`

The restructure listed `data/`. In `.gitignore` an unanchored `data/` matches a directory named `data` at any depth, so it silently ignored `src/medsafe/data/` (the adapter package) and would have ignored new files under `ui/src/data/`.

**How it was caught:** `git add` refused the adapter files. By then the restructure commit had already gone in without `src/medsafe/data/__init__.py`, with every local test passing. Fixed by anchoring to `/data/` (the root dataset folder only) and amending the unpushed commits.

**The near-miss:** a partly ignored package fails nowhere locally. The zip would have shipped without its data package and failed on import on the grader's machine. Since then, every change is verified from a fresh clone, which is where a missing file shows up.

---

## D-006 SQLite is a cache, never the scoring path

`run.py` reads the supplied input files directly. `data/medsafe.db` is built afterwards by `tools/build_db.py`, for queries and for the UI. Tested: output is byte-identical with the database deleted, and nothing under `src/` or in `run.py` imports `sqlite3`.

---

## D-007 Repo-level CLAUDE.md

A `CLAUDE.md` for an unrelated project (Q-ResQ NER) sits in the parent `Downloads` folder and was loaded into every session here. We added a repo-root `CLAUDE.md` with this project's rules and an explicit instruction to ignore parent files. Claude Code still reads every `CLAUDE.md` up the directory tree, so the complete fix is moving that file into its own project folder.

---

## D-008 The harness is built before the detector, against an explicit seam

**Spec** (00-MASTER §5): Phase 7 straight after Phase 1, because every threshold in Phases 2, 4 and 6 is "tuned in Phase 7". Building the detector first means tuning blind.

**We do:** `run.py`, `tools/build_db.py` and the harness all call one function, `medsafe.pipeline.run_pipeline`, so the harness measures exactly what ships. A stage that is not built yet is `None` on every patient result, and the harness reports it as "not built" rather than "found nothing". `eval/trace.py` converts pipeline output into the harness's own records. When a phase lands without a converter there, it raises `NotImplementedError` naming the phase, so the harness can never silently score a stage it does not understand.

**Consequence, stated plainly:** until Phases 2 and 6 land, serious recall is 0 by construction, every missed near-miss reads "name resolution not built yet", and the threshold sweep is flat. The harness itself is verified by the hand-computed cases in `tests/test_metrics.py` and by the calibration baselines (D-010).

---

## D-009 Fixture issue labels: Round 1 logic on the true drug list (superseded by D-012)

Phase 7 scores recall against labelled issues, and no phase specified how the fixtures get them. `tools/fixture_labels.py` ports the Round 1 rule logic (`ui/src/data/engine.ts`: context modifiers, renal thresholds, duplicate classes, pregnancy levels) and applies it to each patient's **true** generics and **true** values, before any name was mangled or any value blanked. The detector sees the slip as written; the labels see what was meant.

- **Independence:** Phases 3 and 4 are built from their own specs, not from `engine.ts`. Where the two disagree, the harness shows it as a miss or a false alarm, which is the realistic case: the real labels will come from someone else's judgement too.
- **Serious** means high or medium.
- **Near-misses:** 30 serious issues, sampled round-robin across issue types from those with a concrete reason to be hard (misspelt or squashed name, eGFR just under a threshold, pregnancy, interaction hidden behind brands, the same drug written two ways). Each carries its reason, which the miss list prints.
- **Limits:** labels and drug table share the same 68 generics, so an unknown drug cannot be a labelled issue. The data is synthetic. Both go in the limitations section.
- **Swap point:** `eval/truth.py` is the only module that knows the label file layout. Change it when the real labels arrive.

---

## D-010 Our reading of the scoring function (superseded by D-014)

`eval/mirror.py`, one function, replaced wholesale when the real `evaluate.py` arrives:

```
score = max(0, serious_recall - 0.05 x low-value alerts per patient)
```

- **Recall** counts a serious issue as caught if any shipped alert covers it, at any severity.
- **Low-value alert:** one that covers no serious true issue (a false alarm, or a true issue the labels rate low). Judged by the ground truth, not by the alert's own label, so a system cannot dodge the penalty by calling everything high.
- **Matching:** same patient, same issue type, and either the exact drug set or a drug set listed in a collapsed alert's `covers`. Not a subset test: one alert naming every drug a patient takes must not count as catching every pair.
- **0.05** is our guess (one low-value alert per patient costs five points of recall). The calibration baselines on the fixtures behave as the brief describes: flag nothing scores 0, flag everything scores 0 (0.96 recall at 75.6 alerts per patient), the oracle scores 0.94.

---

## D-011 Dropped patients count against recall

Alerts per patient divide by loaded patients, but recall divides by **every** labelled issue, including those of patients the adapter dropped. A dropped patient's issues are listed as missed with the reason "patient not loaded". This is what makes D-001's cost visible: `tests/test_eval.py` shows a patient with a bad weight keeps their issues in play, while a patient with no medications loses them.

---

## D-012 The real data pack replaces the synthetic fixtures

The H4 pack arrived (unzipped to `data/pack/`, ignored by git). Phase 1 was rebuilt on its schema: patients with sex, allergies and prescriber count, and seven reference tables (drugs, combination brands, interactions, renal tiers, duplicate groups, contraindications, conditions). Medication lists split on `;` or a line break, exactly as the scorer defines a written token; `tests/test_adapter.py` checks every one of the 9,087 training tokens lines up.

- **Missing means an empty cell only**, as the pack README instructs (`keep_default_na=False`). We read with the standard `csv` module, which does exactly that (D-004). The one word that is not a value, `NA` in the pregnancy column for male patients, is mapped explicitly to "not applicable".
- **The Round 1 generator, labeller and synthetic fixtures are retired** (git history keeps them). Committed tests use hand-written mini fixtures in the pack's exact layout (`tests/fixtures/mini/`), which run anywhere; tests on the real pack, including a 100-patient day-to-day slice, read it at test time and skip with a clear reason without it. No pack data is copied into the repo.

## D-013 Reference rows degrade too (extends D-001)

A drug, interaction, renal tier, duplicate group or contraindication row with one unreadable field is kept, with that field `None` and the row named in the load report. Dropping a drug row would silently remove it from every patient on it. A reference row is skipped only when it has no identity: a drug with no generic name, an interaction missing either drug, a combination with no components. Tested on paracetamol, which four of the mini patients take: a bad pregnancy letter leaves it loaded and still resolvable.

## D-014 The official scorer replaces our mirror

The harness runs the organisers' `evaluate.py` unmodified, in its own process (`eval/official.py`). Our mirror (D-010) is deleted. Its numbers were a guess and the real formula is known: `base = 0.40 serious_recall + 0.15 near_miss_recall + 0.15 precision + 0.15 graded_recall + 0.15 resolution_accuracy`, times `max(0, 1 - noise_per_patient / 2)`.

- **Dev and holdout.** The 1,500 training patients are split, seeded and fixed, into 1,200 dev (every threshold is tuned here) and 300 holdout (reported, never tuned on). `python -m eval.run` scores both.
- **Disclosure.** After the first resolver sweep I printed the holdout's two errors once, to check the dev errors' pattern was general. Both were the same transposition pattern already seen in dev; no rule was written for a holdout string, and since then only dev failures are inspected.
- **The floor**, from `python -m eval.floor` on all 1,500 training patients: the pack baseline scores **0.4071** (serious recall 0.2954, near-miss 0.0000, precision 0.9263, graded 0.3498, resolution 0.7787). Committed in `eval/floor.json` and `docs/baseline-floor.md`.

## D-015 Table severity, verbatim; no re-scoring, no collapse, no cap in the submission

**Evidence:** `python tools/verify_label_severity.py` recomputes every training label's severity from the tables. 3,241 of 3,241 match:

| Issue type | Labels | Match | How the table severity is found |
|---|---|---|---|
| interaction | 1,834 | 1,834 | the pair's severity |
| renal_dose | 698 | 698 | most restrictive tier below the patient's eGFR |
| duplicate_therapy | 507 | 507 | group severity (403); paracetamol override, major (104) |
| contraindication | 202 | 202 | the drug's only candidate (89); one of its candidates (113) |

`graded_recall` credits only the exact severity, and the scorer matches an alert only on the exact (patient, issue type, set of drugs). So, reversing the plan in Phases 4 to 6:

- **Phase 4** re-scoring would turn right severities into wrong ones. Rewritten as a UI-only context layer (`docs/phases/04-context-severity.md`).
- **Phase 5** collapse would replace matchable pair alerts with a cluster alert that matches nothing. UI and explanation only.
- **Phase 6** cap: noise counts only false alerts and alerts on minor issues, so capping a *true* alert loses recall and saves nothing. Removed.

## D-016 Resolver thresholds: best official score, false resolutions at most 2%

Chosen policy: the setting with the best official primary score whose false-resolution rate is at most 2%. `python -m eval.sweep` scores 140 settings on dev with the real scorer and picks **MIN_CONFIDENCE 0.45, MIN_MARGIN 0.00, MIN_PREFIX_LENGTH 5**: dev resolution accuracy 0.9999 with no false resolutions, holdout 1.0000 with none. The spec's starting guesses (0.72, 0.05) abstained on 5.9% of dev lines, nearly all misspellings whose top candidate was right.

**Re-run after Phase 3.** With no alerts, a false resolution costs only its own line. Once alerts exist it can also raise a false alert (a full noise unit, a precision hit, and a missed true issue), so the trade-off changes.

## D-017 Where the resolver departs from the Phase 2 spec

Each change came from a dev failure and is general, not a patch for one string:

- **Transposition-aware edit similarity** (optimal string alignment, not plain Levenshtein). "Telam" for "Telma" is one swap, not two edits; Levenshtein ranked such handwriting below unrelated drugs.
- **An exact tie between two different drugs always abstains**, whatever MIN_MARGIN is. Picking one alphabetically is a coin toss presented as an answer.
- **Hyphenated names**: a fuzzy piece must score 0.80 or more. "monteleukast-LC" (generic plus a combination suffix) resolves; "Mftal-Spas" (a misspelt brand) is not split into a fake combination.
- **Numbered brands**: the words after the name are part of the search, so "Huminsulin 30/70" finds the premix, not one of its two insulins.
- **Non-medicine lines** are recognised by general words (devices, monitoring, tests, diet, follow-up), checked only after an exact name match fails, so a real brand always wins.
- **Curated synonyms and abbreviations** (PCM, ISMN, MTX, frusemide, mecobalamin, insulin 30/70, ...) from general prescribing knowledge, not memorised patient strings. "Vitamin B12" is deliberately absent: both methylcobalamin and cyanocobalamin are listed.
- **Several generics per line.** `Resolution.generics` replaces the spec's single `resolved_generic`, because combination brands hide several.
- **Not built:** the spec's small bonus when a candidate's class matches a diagnosis. At 99.99% dev accuracy there is nothing left for it to fix.

## D-018 Minor alerts are detected, shown, never submitted

`EMIT_MINOR = False` (`src/medsafe/output/policy.py`).

**Why, clinically.** Minor alerts drive alert fatigue. Fatigue drives dismissal: prescribers who see a stream of low-value popups learn to click past them. And dismissal buries the serious alert that sits among them. A minor issue is real, so the clinician view still shows it, ranked last; it never interrupts. The scorer penalises minor alerts (0.25 noise units each, nothing earned in any recall term) because this is what happens in hospitals.

**Corroboration, measured** on all 1,500 training patients by `python -m eval.floor`:

| Detector | With minor alerts | Without | Change |
|---|---|---|---|
| oracle (perfect detection) | 0.9482 | 1.0000 | +0.0518 |
| pack baseline (weak detection) | 0.4071 | 0.4121 | +0.0050 |

For the weak detector, precision falls (0.9263 to 0.9133) because its matched minor alerts were propping it up, but noise falls more (0.0903 to 0.0580). Dropping them wins for both.

## D-019 The oracle's 0.94 (E1), answered

Under our old mirror the oracle scored 0.94 because it emitted the true *low* issues and the mirror penalised them. That was not a mirror bug: the real scorer does the same thing to minor issues, at 0.25 noise each. Under the real scorer, an oracle that reports every true issue scores 0.9482 on train; without the minor ones, 1.0000. So the ceiling is 1.0, and only for a submission that leaves minor issues out (D-018).

## D-020 What a training score measures (E2)

The organisers' labels come from a deterministic rule engine running the published tables on each patient's true regimen; the hidden test labels come from the same engine. Our rule engine implements the same published rules. So a training score measures whether name resolution, list parsing and our implementation of the published rules are right. It does **not** measure whether the rules are clinically right: labeller and detector share them by design. Expect test numbers to differ where the test lists are written differently, not where the rules differ.

Guarded in `tests/test_guards.py`: nothing on the scoring path (`run.py`, `src/medsafe/`) may read `train_labels.csv` or `train_resolution.csv`, import the harness or the tools, touch the SQLite cache, or import a network or LLM client.

## D-021 Unknown age must never read as "not elderly" (E4)

This is a rule violation, not a gap: skipping an age-based rule when age is unknown treats unknown as safe. With severity fixed to the table (D-015), age now affects only the UI's context notes, but the rule still holds there. With age unknown, the age rule does not fire **and** `age` is named as unverifiable, exactly as an unknown eGFR is. `tests/test_phase4_contract.py` enforces it. It starts running the moment `src/medsafe/explain/context.py` exists, so Phase 4 cannot land without it.

## D-022 Do not submit the current build (superseded by D-025)

With name resolution done and no rule engine yet, the predictions file is empty. The official score is then 0.15 (the resolution term alone), below the pack baseline's 0.4071. Until Phase 3 lands, the pack baseline is the better submission.

## D-023 The LLM resolution fallback ships off: a measured decision

The proposed fallback (an LLM picking from our top candidates, or "none") would only ever see lines the deterministic resolver abstains on. It abstains on 1 of 7,131 dev lines, 0 of 1,956 holdout lines, and 7 of 20,867 test lines. Even if it resolved all 7 test lines correctly, resolution accuracy would rise by 0.03 points, about +0.00005 on the primary score, against the risk that one wrong pick raises a false alert. Not built; this measurement is the reason.

## D-024 How an LLM may be used: train text only, offline, never on the scoring path

The pack forbids "having someone or something label [test patients] case by case". Sending test patients' diagnosis text to a model and committing its answers would read as exactly that: 807 diagnosis fragments occur only in test. So:

- **The LLM sees training text only.** It proposes vocabulary per `condition_id` (synonyms, abbreviations, vernacular terms, negation cues) from train diagnosis and allergy text. People review the proposals, and the accepted ones are committed as a deterministic matcher that runs on test like any other code. No test string is ever sent to a model.
- **Offline only.** `tools/llm_*.py` run by hand, through OpenRouter, with the key read from an environment variable and never written to disk. `run.py` and `src/medsafe/` never call a model; `tests/test_guards.py` fails if they import a network or LLM client.
- **Traceable.** Prompts live in `tools/prompts/` with a version; every generated file records the model name and a hash of the prompt.
- **Measured.** The matcher's contraindication recall and precision on train, with and without the LLM-proposed vocabulary, go in `docs/ABLATION.md`. If the vocabulary does not help, it ships disabled and the doc says why.
- **Order.** Phase 3 (the rule engine, with a deterministic condition matcher and negation detector) comes first, so the LLM layer is measured against a working baseline.

## D-025 Phase 3: the rule engine reproduces every training label

The four families in `docs/rules.md` reproduce all 3,241 training labels: none missed, none false, none at the wrong severity. The official scorer on all 1,500 training patients: **primary 1.0000** (serious recall 1.0000, near-miss 1.0000, precision 1.0000, graded 1.0000, resolution 0.9999, noise 0.0000), against the pack baseline's 0.4071.

The first run scored 0.9852. Every gap was a rule bug, found by patient id and fixed by a general rule:

- **"Stopped" has more words.** "(withdrawn)", "pt not taking since 2 months", "old, not taking now" mark a stopped medicine. Missing them caused all 30 false interaction, duplicate and renal alerts.
- **Heart failure is also written as reduced heart function.** "LVEF 30%", "LV dysfunction", "DCMP", "ischaemic cardiomyopathy (EF 30%)" count as heart failure, while "LVEF normal - no HF" stays negated. This fixed 6 missed NSAID contraindications.
- **Gout includes hyperuricaemia**, as conditions.csv itself says ("Gout / hyperuricaemia"). This fixed 2 missed thiazide contraindications.

**Condition truth, back-derived (R7).** Of the 202 contraindication labels, 121 pin their condition down uniquely (24 of them pregnancy); 81 leave more than one possible. From these and from the labels a drug did *not* get, 83 (patient, condition) pairs are proven present and 3,418 proven absent. The matcher finds all 83 and fires on none of the 3,418 (`tools/derive_condition_truth.py`).

**The vocabulary covers the 15 conditions that can change an alert.** The 12 diagnoses and 3 allergies the contraindication table uses. Terms such as "madhumeh" (diabetes) or "raised lipids" name conditions no table row uses, so recognising them could not change a single alert; they are left out rather than added as untested code.

**Limits, stated plainly.** The stopped markers and the condition vocabulary were fixed by reading all 1,500 training patients, so the training score is in-sample: the 300-patient holdout is not a clean estimate for the rules. The test set has 807 diagnosis fragments that never appear in train; the vocabulary tolerates typos and abbreviations, but a phrasing it has never seen can still be missed (a missed contraindication) or wrongly matched (a false alert). Test text was not read to prepare for this (D-024).

**When a submission is made, it is this build, not the pack baseline.** This supersedes D-022. Nothing has been submitted.

## D-026 Two tracks, one engine

The rubric pays mostly for a clinical workflow; the hidden-split score is 20% of judging. So the same engine serves two tracks (docs/WORKFLOW.md):

- **Track B, point of care, is the workflow:** identify, capture, resolve, context, check, prioritise, act, escalate, record.
- **Track A is batch evaluation mode:** the predictions and resolution files.

Everything only the clinician sees (prioritise and collapse in `explain/prioritise.py`; act, escalate and audit policy in `workflow.py`; the portal in `ui/`) is outside Track A. `tests/test_compliance.py` runs Track A from a copy of the code with that layer and `ui/` deleted, and requires byte-identical files.

- **Confidence and limitations on every alert, in both tracks.** `explain/limitations.py` writes it, and the predictions file carries it as an extra column the scorer ignores (the official score is unchanged at 1.0000). It names the rule that fired, what could not be checked for this patient (an unresolved line, eGFR, diagnoses, allergy history, pregnancy status), that the list may be incomplete, and that a clinician decides. A patient with no alert gets "No issue was found in the N medicines listed", never "safe".
- **Suggested action, verbatim.** Every alert's action is the table's `recommended_action`, except pregnancy-category contraindications (22 in train, 52 in test), for which the tables give no action. Those use one fixed template, and their limitations line says so.
- **Collapse objective, corrected.** Phase 5 asked for the drug set clearing the most serious pairs, ties to fewer drugs. Taken literally, that prefers "review warfarin and contrast" (5 of 5) to "review warfarin" (4 of 5), which groups nothing. Every chosen drug must now be in at least two serious pairs no other chosen drug is in. Phase 5's own acceptance case, one drug clearing 4 of 5 with the fifth listed separately, now holds.
- **Prescriber attribution is not in the data.** `prescriber_count` says how many doctors wrote the list, not who wrote which line. The portal shows the count and marks three-prescriber patients; it never claims an alert "crosses prescribers".
- **Defer is given to prescriber and pharmacist** (the roles that can accept). The portal brief gave it to no role explicitly; change `workflow.PERMISSIONS` if that is wrong.
- **The test submission is validated, not submitted.** `python run.py --split test --out submission` writes 5,758 alerts and 20,867 resolution rows; `python -m eval.validate_submission submission` runs the organisers' own validators on them and checks every test line has a row.
- **The portal is built by the second workstream.** The engine side is handed over in `docs/engine-handoff.md`, and README sections are drafted in `docs/readme-draft.md` for merging, so the two edits do not collide.
