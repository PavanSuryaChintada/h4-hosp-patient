# Phase 3 — Rule Engine

**Time:** 3h. Four check families, each a pure function, each independently testable.

---

## Requirements

**R1 — Four checks, four modules.**

| Check | Input | Fires when |
|---|---|---|
| `interaction.py` | resolved generics, interaction table | a pair appears in the table |
| `duplicate.py` | resolved generics, drug classes | two drugs share a class |
| `renal.py` | generics with `renal_adjust`, patient eGFR | drug needs adjustment and eGFR is below threshold |
| `contraindication.py` | generics, pregnancy status, diagnoses | pregnancy category or diagnosis conflict |

**R2 — Every finding is a `Finding`, not a string.**

```python
@dataclass(frozen=True)
class Finding:
    rule_id: str              # "INT-WARF-NSAID", "RENAL-METFORMIN"
    issue_type: str           # interaction | duplicate | renal | contraindication
    drugs: tuple[str, ...]    # resolved generics involved
    raw_drugs: tuple[str, ...]# the original strings, for the UI
    table_severity: str       # as the source table states it
    evidence: dict            # the patient values that triggered it
    mechanism: str | None
```

`evidence` carries the actual numbers — `{"egfr": 28, "threshold": 45}` — so every alert is traceable to the data that produced it. **A finding without evidence is a bug.**

**R3 — Findings are not alerts.** This phase produces raw findings only. Severity re-scoring is Phase 4, collapse is Phase 5, capping is Phase 6. Do not filter here. Over-filtering early is how recall quietly dies.

**R4 — Unresolved drugs produce an informational finding**, not silence: `rule_id="UNRESOLVED"`, listing the raw string. It carries the lowest severity and will usually be capped out, but it exists so the patient record is honest about what could not be checked.

**R5 — Pure functions.** `check_interactions(generics, table) -> list[Finding]`. No IO, no globals, no mutation. Trivially testable and trivially parallelisable later.

**R6 — Rule ids are stable and documented.** `docs/rules.md` lists every rule id with its meaning. The AI reviewer will read it, and the report cites it.

---

## Deliverables

- [ ] `src/medsafe/rules/{interaction,duplicate,renal,contraindication}.py`
- [ ] `src/medsafe/rules/engine.py` — runs all four, returns combined findings
- [ ] `src/medsafe/rules/types.py` — the `Finding` dataclass
- [ ] `docs/rules.md` — the rule id catalogue
- [ ] `tests/test_rules.py` — a positive and a negative case per rule family, plus the unresolved case

## Acceptance

- A patient on warfarin and ibuprofen produces exactly one interaction finding with both drugs and the mechanism.
- A patient on metformin at eGFR 28 produces a renal finding whose evidence contains both the eGFR and the threshold.
- The same patient at eGFR 80 produces **no** renal finding.
- Two drugs of the same class produce exactly one duplicate finding, not two.

## Claude Code prompt

```
Build Phase 3 per 03-rule-engine.md, on top of Phases 1 and 2.

1. types.py with the Finding dataclass exactly as specified, including the evidence dict.
2. Four rule modules, each exposing one pure function. No IO, no globals, no mutation.
   - interaction: all unordered pairs of resolved generics against the interaction table
   - duplicate: two or more drugs sharing a class, one finding per class, not per pair
   - renal: drugs flagged renal_adjust where patient eGFR is below the drug's threshold.
     eGFR of None means unknown - emit a finding with issue noted as unverifiable, never
     treat None as safe.
   - contraindication: pregnancy category conflicts and diagnosis conflicts
3. Every Finding carries evidence with the actual triggering values, for example
   {"egfr": 28, "threshold": 45}. Assert in tests that evidence is never empty.
4. Unresolved medications produce a Finding with rule_id UNRESOLVED and the raw string.
5. engine.py runs all four and returns the combined list. It does NOT filter, rank or cap.
6. docs/rules.md listing every rule id and what it means.
7. tests/test_rules.py with a positive and negative case per family, including the
   eGFR 28 versus eGFR 80 pair on the same drug.

Docstrings on every public function.
```
