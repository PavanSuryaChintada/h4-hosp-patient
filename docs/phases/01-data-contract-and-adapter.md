# Phase 1 — Data Contract & Adapter

**Blocks:** everything. **Time:** 3h. **Status: build now, before the dataset arrives.**

---

## Why this phase exists

The real dataset is not in hand yet. Build an **adapter** so that when it lands, you change one module and nothing else. Teams that hardcode column names spend their last day doing a rename across forty files.

---

## Requirements

**R1 — Internal schema, frozen now.** Everything downstream speaks this, not the raw files.

```python
@dataclass(frozen=True)
class MedicationEntry:
    raw: str                 # exactly as written in the source
    index: int               # position in the patient's list

@dataclass(frozen=True)
class Patient:
    patient_id: str
    age: int | None
    weight_kg: float | None
    egfr: float | None
    pregnant: bool | None
    diagnoses: tuple[str, ...]
    medications: tuple[MedicationEntry, ...]

@dataclass(frozen=True)
class Drug:
    generic: str
    drug_class: str
    brands: tuple[str, ...]
    renal_adjust: bool
    pregnancy_category: str | None

@dataclass(frozen=True)
class InteractionPair:
    drug_a: str              # generic
    drug_b: str              # generic
    severity: str            # as given in the source table
    mechanism: str | None
```

**R2 — The adapter is the only place that knows the real file layout.**
`src/medsafe/data/adapter.py` exposes `load_patients(path) -> list[Patient]`, `load_drugs(path) -> dict[str, Drug]`, `load_interactions(path) -> list[InteractionPair]`.
Column names live in a single `COLUMN_MAP` dict at the top of that file. When the real data arrives, you edit that dict.

**R3 — Validate on load, loudly.** Row count, required columns present, types coercible, value ranges sane (eGFR 0–200, age 0–120, weight 0–300). A malformed row is logged with its index and skipped, never silently dropped. Report counts: loaded, skipped, and why.

**R4 — Missing is a value, not zero.** `None` everywhere, never `0` or `""`. An eGFR of `None` means unknown and must behave differently from an eGFR of 0. This will matter in Phase 4 and it is a common silent bug.

**R5 — Fixtures that mimic the real thing.** `tools/make_fixtures.py` generates 200 synthetic patients in the shape the brief describes: handwritten-style brand/generic mix, misspellings, dose suffixes, 4–12 drugs, eGFR spread, some pregnant, some elderly. Commit the output to `tests/fixtures/`. The whole pipeline is built and tested against these until the real data arrives.

**R6 — A swap test.** One test that loads fixtures through the adapter and asserts the internal schema is fully populated. When the real data arrives, point the same test at it. If it passes, the rest of the pipeline works.

---

## Deliverables

- [ ] `src/medsafe/data/schema.py` — the dataclasses above
- [ ] `src/medsafe/data/adapter.py` — loaders plus `COLUMN_MAP`
- [ ] `src/medsafe/data/validate.py` — range and type checks, structured load report
- [ ] `tools/make_fixtures.py` + committed fixtures
- [ ] `tests/test_adapter.py` — the swap test, plus malformed-row handling

## Acceptance

- Loading fixtures yields 200 patients with no `0`-for-missing anywhere.
- A deliberately corrupted row is skipped, logged with its index, and counted in the load report.
- Changing one entry in `COLUMN_MAP` redirects a field with no other code change.

## Claude Code prompt

```
Build Phase 1 per 01-data-contract-and-adapter.md and the standing context block.

1. src/medsafe/data/schema.py with the exact frozen dataclasses in the spec. Missing values are
   None, never 0 or empty string.
2. src/medsafe/data/adapter.py exposing load_patients, load_drugs, load_interactions. All real
   column names live in a single COLUMN_MAP dict at the top of the file and nowhere else.
   Support CSV and JSON input; sniff by extension.
3. src/medsafe/data/validate.py: required columns, type coercion, range checks (eGFR 0-200,
   age 0-120, weight 0-300). Malformed rows are skipped with the row index and reason recorded.
   Return a LoadReport with counts of loaded, skipped and a reason breakdown.
4. tools/make_fixtures.py: generate 200 synthetic patients matching the brief's description -
   mixed brand and generic names, misspellings, dose suffixes like "T. Metformin 500mg",
   4-12 drugs each, eGFR spread 15-110, some pregnant, some over 75. Seeded RNG, deterministic.
   Write to tests/fixtures/ and commit.
5. tests/test_adapter.py: load fixtures, assert every Patient is fully populated, assert a
   corrupted row is skipped and counted, assert changing COLUMN_MAP redirects a field.

Docstrings on every public function. No other modules in this task.
```
