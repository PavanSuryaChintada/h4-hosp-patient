# Phase 7 — Evaluation Harness

> **Amended (docs/DECISIONS.md D-014).** The real `evaluate.py` arrived: the harness now runs it unmodified, and the scoring mirror is deleted. Thresholds are tuned on a fixed 1,200-patient dev split and reported on a 300-patient holdout.

**Time:** 2h. **Build this second, right after Phase 1. Not last.**

---

## Why this comes early

You cannot tune a detector you cannot measure. Teams that build the harness last discover their recall problem on the final night, with no time to fix it.

Every threshold in Phases 2, 4 and 6 is marked "tuned in Phase 7". This is where that happens.

---

## Requirements

**R1 — Mirror the real scoring.** The brief says recall on serious issues, penalised by low-severity volume. Implement your best reading of it now, and **replace it with the real `evaluate.py` logic the moment you have the file.** Keep your mirror alongside it afterwards so you can see both.

**R2 — The two headline numbers, always reported together:**

```
Serious-issue recall        Alerts per patient
0.93                        11.0 → 3.2
```

Reporting one without the other is meaningless — it is trivial to move either alone. Print them side by side, always.

**R3 — Near-miss recall, reported prominently.** The 300 seeded cases are the brief's named metric. Report the number, **and list the missed ones with a reason per miss.** A perfect score reads as unmeasured; a reported miss with a diagnosis reads as rigorous.

**R4 — The breakdowns that let you act:**

- Recall by issue type — are you missing renal or interactions?
- Recall by severity — are the misses serious or trivial?
- Alerts per patient by severity, before and after collapse
- False-positive volume by severity
- Resolution accuracy and false-resolution rate (from Phase 2)
- Patients with zero alerts — count, and whether they genuinely had none

**R5 — Threshold sweeps.** A script that sweeps the alert cap (2–8) and the resolution confidence threshold (0.60–0.90), reporting the two headline numbers at each setting, and prints the setting that maximises the score. **Commit the sweep table to `docs/`.** It is direct evidence you found the ridge deliberately.

**R6 — Reproducible with provenance.** Every run writes `eval/reports/<timestamp>-<git_sha>.json` recording git sha, fixture or dataset version, every threshold value, and all metrics. Two runs on the same input must be comparable.

**R7 — A regression gate.** `python -m eval.run --compare <previous>` exits non-zero if serious-issue recall dropped. Wire it into the test suite if time allows.

---

## Deliverables

- [ ] `eval/metrics.py` — all metric computations
- [ ] `eval/run.py` — runs the pipeline, computes, writes the report
- [ ] `eval/sweep.py` — threshold sweeps
- [ ] `eval/mirror.py` — your reading of the scoring function, swapped for the real one when available
- [ ] `docs/evaluation.md` — generated from the latest report
- [ ] `tests/test_metrics.py` — hand-computed cases proving the metrics are right

## Acceptance

- `python -m eval.run` prints both headline numbers and writes a timestamped report.
- The sweep table shows a clear optimum, not a flat line.
- Missed near-misses are listed individually with reasons.
- Metrics are tested against hand-computed examples — **a wrong metric is worse than no metric**, because you will tune towards the wrong thing with total confidence.

## Claude Code prompt

```
Build Phase 7 per 07-evaluation-harness.md. Build it BEFORE Phases 2-6 if they are not done -
every threshold in them is tuned here.

1. eval/metrics.py: serious-issue recall, near-miss recall, alerts per patient (overall and by
   severity, before and after collapse), false-positive volume by severity, recall by issue
   type, resolution accuracy, false-resolution rate, zero-alert patient count.
2. eval/mirror.py: our reading of the scoring function - reward serious recall, penalise
   low-severity alert volume. Isolate it in ONE function so it can be replaced wholesale when
   the real evaluate.py arrives.
3. eval/run.py: run the full pipeline over fixtures (or the real dataset), compute everything,
   print the two headline numbers side by side, and write
   eval/reports/<timestamp>-<git_sha>.json with git sha, data version, every threshold value
   and all metrics.
4. Missed near-misses listed individually with a reason per miss. Never report only the count.
5. eval/sweep.py: sweep ALERT_CAP 2-8 and MIN_CONFIDENCE 0.60-0.90, report both headline
   numbers at each setting, print the argmax, and write the full table to docs/sweep.md.
6. --compare <report> mode exiting non-zero if serious-issue recall dropped.
7. tests/test_metrics.py: hand-computed fixtures for every metric. A wrong metric is worse than
   no metric.

Docstrings on every public function.
```
