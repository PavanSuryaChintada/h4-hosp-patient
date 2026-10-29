# Phase 10 — Report & Limitations

**Time:** 2h. **Never cut.** This is where measured work turns into score.

---

## Requirements

**R1 — Every number comes from `eval/reports/`.** Generate the report from the JSON where you can. A number typed by hand will eventually contradict the code, and a reviewer who finds one stops trusting the rest.

**R2 — Lead with the two numbers, together:**

> Serious-issue recall 0.93. Alerts per patient 11.0 → 3.2.
> Reporting either alone is meaningless: both are trivially movable in isolation.

**R3 — Near-miss recall prominently, with the misses named.** The count, then a table of what was missed and why. **Include the misses.** A clean 300/300 reads as unmeasured.

**R4 — The method, with a worked example each:**

- Resolution: a real misspelled string resolving, and a real one abstaining
- Severity: the eGFR 28 vs 80 pair on the same drug
- Collapse: the hero patient's 5 interactions becoming 1 action, with the graph
- The threshold sweep table, with the chosen setting marked

**R5 — `docs/LIMITATIONS.md`, structured as: what was simplified · why · what production would need.**

Candidates, all genuine:

- Reference tables assumed complete and authoritative
- No allergy history unless present in the record
- The medication list may be incomplete — **the system never claims safety, only that no issue was found in what it saw**
- No dose-level checking beyond renal adjustment
- Collapse only applies to the interaction subgraph
- Severity modulators are a hand-built policy, not learned, and not clinically validated
- Synthetic data only; no clinical validation of any kind

**R6 — A safety-reasoning section.** A clinical-adjacent system is partly judged on whether you understood the stakes:

- A missed serious interaction is worse than an extra alert, but an alert storm causes misses by making the system ignorable. Name that tension and say how you resolved it.
- Unknown never means safe.
- No dosing instruction is model-generated; every action traces to a committed table row.
- A clinician decides.

**R7 — Reproducibility statement.** The exact commands, the environment, and the claim that two runs produce identical output — with the test name that proves it.

---

## Deliverables

- [ ] `docs/REPORT.md` — generated where possible
- [ ] `docs/LIMITATIONS.md`
- [ ] `docs/DECISIONS.md` (from Phase 8, cross-linked)
- [ ] `tools/make_report.py` — builds the report from the latest eval JSON

## Acceptance

- Every figure in the report traces to a file in `eval/reports/`.
- The limitations section names at least six real weaknesses.
- The missed near-misses are listed individually.
- A reader who only reads the first page knows what was built, how well it works, and what it cannot do.

## Claude Code prompt

```
Build Phase 10 per 10-report-and-limitations.md.

1. tools/make_report.py generating docs/REPORT.md from the latest eval/reports JSON. Every
   number must come from that file. Fail loudly if a placeholder remains unfilled.
2. The report opens with serious-issue recall and alerts per patient side by side, plus one
   sentence on why reporting either alone is meaningless.
3. Near-miss recall section: the count, then a table of every missed case with a reason.
   Do not omit the misses.
4. Method section with four worked examples from the real data: a resolution, an abstention,
   the eGFR 28 versus 80 pair, and the collapse hero patient with its graph.
5. Include the threshold sweep table with the chosen setting marked and one line on why.
6. docs/LIMITATIONS.md structured as what was simplified, why, and what production would
   require - covering at least the six items listed in this spec.
7. A safety-reasoning section naming the tension between missed interactions and alert
   fatigue, stating that unknown never means safe, that no dosing instruction is
   model-generated, and that a clinician decides.
8. A reproducibility statement with the exact commands and the name of the test that proves
   two runs are byte-identical.
```
