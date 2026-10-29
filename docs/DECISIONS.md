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
