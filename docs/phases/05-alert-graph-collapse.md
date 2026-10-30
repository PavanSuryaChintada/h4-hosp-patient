# Phase 5 — Alert Graph Collapse

> **Amended (docs/DECISIONS.md D-015).** The official scorer matches an alert only on the exact (patient, issue type, set of drugs). A collapsed cluster alert would match nothing, so the predictions file keeps one row per issue. Collapse lives in the UI and the explanation text only.

**Time:** 3h. **The differentiator.** Nobody else will build this.

---

## The idea

A patient on 9 drugs with 5 serious interactions does not have 5 problems. Often **one drug sits in 4 of the 5 pairs.**

So instead of:

```
⚠ Warfarin + Ibuprofen
⚠ Warfarin + Aspirin
⚠ Warfarin + Fluconazole
⚠ Warfarin + Amiodarone
⚠ Metformin + Contrast
```

the prescriber gets:

```
Stop or review Warfarin — clears 4 of the 5 serious interactions
Review Metformin + Contrast separately
```

Five alerts become two actions. **Alert volume falls without recall falling**, which is exactly the ridge the scoring is built around.

---

## The algorithm

Build a graph per patient: drugs are nodes, serious findings are edges. Find the **minimum set of drugs whose removal clears the most serious edges** — a weighted vertex cover.

NP-hard in general. Here, `n < 12` drugs per patient, so **brute force every subset**: 2¹² = 4,096, microseconds. Exact, no solver dependency, no approximation to defend.

```python
def collapse(findings, max_set_size=3):
    """Smallest drug set clearing the most serious interaction edges.

    Exhaustive over subsets; n is small enough that this is exact and instant.
    """
    drugs = sorted({d for f in findings for d in f.drugs})
    edges = [f for f in findings
             if f.issue_type == "interaction" and f.final_severity in ("high", "medium")]
    best = None
    for size in range(1, max_set_size + 1):
        for subset in itertools.combinations(drugs, size):
            cleared = [e for e in edges if set(e.drugs) & set(subset)]
            cand = (len(cleared), -size, subset, cleared)
            if best is None or cand[:2] > best[:2]:
                best = cand
    return best
```

Tie-break deterministically: fewer drugs wins, then alphabetical. **Never random** — the output must be reproducible.

---

## Requirements

**R1 — Only serious edges collapse.** Low and info findings are not worth asking a prescriber to change a drug for.

**R2 — Report the uncovered remainder honestly.** If the chosen set clears 4 of 5, the fifth is still listed as its own alert. Never hide an edge to make the number look better.

**R3 — Never collapse across issue types.** A renal-dose issue and an interaction are different actions. Collapse applies to the interaction subgraph only.

**R4 — Emit the collapse evidence:** the chosen drugs, which edges each clears, and how many remain. The UI draws the graph from this and the report quotes it.

**R5 — Measure the effect.** Alerts before collapse vs after, per severity. This is a headline number in Phase 7 and in the report.

**R6 — Suggested action phrasing is specific.** `"Stop or review Warfarin — clears 4 of the 5 serious interactions"`, never `"Consider medication review"`.

---

## Deliverables

- [ ] `src/medsafe/collapse/graph.py` — build the per-patient interaction graph
- [ ] `src/medsafe/collapse/cover.py` — the exhaustive solve
- [ ] `src/medsafe/collapse/action.py` — action phrasing from the result
- [ ] `tests/test_collapse.py` — the 4-of-5 case, determinism, the no-collapse-possible case

## Acceptance

- The hand-built 9-drug / 5-interaction case returns exactly one drug clearing 4 edges, with the 5th listed separately.
- A patient where no single drug clears more than one edge returns the edges uncollapsed, not a forced grouping.
- Two runs give identical output.
- Solve time under 5ms per patient.

## Claude Code prompt

```
Build Phase 5 per 05-alert-graph-collapse.md, on top of Phase 4.

1. graph.py: per patient, build nodes from resolved generics and edges from interaction
   findings at high or medium final severity only.
2. cover.py: exhaustive search over drug subsets up to size 3, returning the subset clearing
   the most edges, tie-broken by smaller size then alphabetically. Exact, deterministic, no
   randomness. Docstring must state why brute force is correct here (n < 12).
3. Collapse applies ONLY to the interaction subgraph. Renal, duplicate and contraindication
   findings pass through untouched.
4. Return a CollapseResult: chosen_drugs, edges_cleared (with which drug cleared each),
   edges_remaining. Remaining edges are emitted as their own alerts - never hidden.
5. action.py: phrase the suggested action specifically, naming the drug and the count,
   for example "Stop or review Warfarin - clears 4 of the 5 serious interactions".
6. Record alerts-before and alerts-after counts per severity for the Phase 7 metrics.
7. tests/test_collapse.py: a hand-built 9-drug 5-interaction fixture asserting one drug clears
   4 edges; a case where no collapse is possible; a determinism test; a timing assertion
   under 5ms per patient.

Docstrings on every public function.
```
