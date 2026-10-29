# Phase 4 — Patient-Context Severity

**Time:** 2h. This is where most teams lose, by passing table severity straight through.

---

## The idea in one line

The table says "severe". **Severe for whom?** A renal-dose flag at eGFR 28 is critical. The identical flag at eGFR 80 is noise. Copying the table's severity is why hospital alert systems get switched off.

---

## Requirements

**R1 — Four output levels:** `high`, `medium`, `low`, `info`. Map the table's own severity words onto a base level, then modulate.

**R2 — Modulators, applied in order:**

| Factor | Effect |
|---|---|
| eGFR far below threshold (< 0.6 × threshold) | +1 level |
| eGFR just below threshold | unchanged |
| eGFR well above threshold | −2 levels (usually to `info`) |
| eGFR unknown | unchanged, flagged `unverifiable` |
| Age ≥ 75 on a sedative, anticoagulant or hypoglycaemic | +1 |
| Pregnancy category D or X while pregnant | force `high` |
| Drug count ≥ 8 | +1 on interaction findings only |
| Resolution confidence < 0.85 on any involved drug | −1 (uncertain input, softer claim) |

Clamp to `[info, high]`. **Never let a modulator push a pregnancy-category-X finding below `high`.**

**R3 — Keep both values.** `table_severity` and `final_severity` both persist. The UI shows the pair, the report explains the difference, and the AI reviewer can see the mechanism rather than take it on trust.

**R4 — Every change is explained.** The record carries `severity_reasons: list[str]`, for example `["eGFR 28 is 0.62× the 45 threshold", "age 79 on an anticoagulant"]`. These strings go straight into the UI and the explanation text.

**R5 — The rules are data, not branching code.** A `MODULATORS` table of `(condition, delta, reason_template)` so a reviewer can read the policy in one place and you can tune it without touching logic.

**R6 — Unknown never means safe.** Missing eGFR, missing age, missing pregnancy status: never downgrade on absence. State this explicitly in the report — it is the safety-reasoning point a clinical judge looks for.

---

## Deliverables

- [ ] `src/medsafe/severity/modulators.py` — the policy table
- [ ] `src/medsafe/severity/score.py` — applies modulators, returns `final_severity` + reasons
- [ ] `docs/severity-policy.md` — the table in human-readable form
- [ ] `tests/test_severity.py` — one test per modulator, plus the clamping and pregnancy-floor cases

## Acceptance

- Same drug, same dose, eGFR 28 vs eGFR 80 → `high` vs `info`, with different reason strings. **Build this exact pair as a named test; it is also the comparison that goes in the report and on the method screen.**
- A pregnancy-category-X finding stays `high` even with three downward modulators applied.
- Missing eGFR never lowers severity.

## Claude Code prompt

```
Build Phase 4 per 04-context-severity.md, on top of Phase 3.

1. modulators.py: a MODULATORS table of (name, predicate, delta, reason_template) implementing
   every row in the spec. Policy as data, not as nested ifs.
2. score.py: map table severity to a base level, apply modulators in order, clamp to
   [info, high], and return final_severity plus severity_reasons as human-readable strings.
3. Hard floor: a pregnancy category D or X finding in a pregnant patient can never drop below
   high, regardless of other modulators. Test it with three downward modifiers applied.
4. Missing values never downgrade. eGFR None keeps the base level and sets unverifiable=True.
5. Persist both table_severity and final_severity on the finding.
6. docs/severity-policy.md rendering the table in readable form.
7. tests/test_severity.py: one test per modulator, the clamping cases, the pregnancy floor, and
   a named test egfr_28_vs_80_same_drug asserting high versus info with distinct reasons.

Docstrings on every public function.
```
