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

## D-009 Fixture issue labels: Round 1 logic on the true drug list

Phase 7 scores recall against labelled issues, and no phase specified how the fixtures get them. `tools/fixture_labels.py` ports the Round 1 rule logic (`ui/src/data/engine.ts`: context modifiers, renal thresholds, duplicate classes, pregnancy levels) and applies it to each patient's **true** generics and **true** values, before any name was mangled or any value blanked. The detector sees the slip as written; the labels see what was meant.

- **Independence:** Phases 3 and 4 are built from their own specs, not from `engine.ts`. Where the two disagree, the harness shows it as a miss or a false alarm, which is the realistic case: the real labels will come from someone else's judgement too.
- **Serious** means high or medium.
- **Near-misses:** 30 serious issues, sampled round-robin across issue types from those with a concrete reason to be hard (misspelt or squashed name, eGFR just under a threshold, pregnancy, interaction hidden behind brands, the same drug written two ways). Each carries its reason, which the miss list prints.
- **Limits:** labels and drug table share the same 68 generics, so an unknown drug cannot be a labelled issue. The data is synthetic. Both go in the limitations section.
- **Swap point:** `eval/truth.py` is the only module that knows the label file layout. Change it when the real labels arrive.

---

## D-010 Our reading of the scoring function

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
