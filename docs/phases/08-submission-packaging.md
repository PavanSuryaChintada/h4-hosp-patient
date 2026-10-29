# Phase 8 — Submission Packaging

**Time:** 3h. **An AI reads this zip. The repo is a scored artifact.**

---

## The premise

Assume a model opens your zip with no context and has to decide, in a few minutes, whether this is good work. Everything below is about making that decision easy and favourable.

Most teams spend zero time here. It is free points.

---

## Requirements

**R1 — `README.md` that answers five questions in the first screen:**

1. What is this? (two sentences)
2. How do I run it? (one command)
3. What does it output?
4. What are the headline results?
5. What are the known limitations?

Then: architecture in one diagram, the method in a few paragraphs, a document index. **Put the results table in the README itself** — do not make the reader open another file to find your numbers.

**R2 — One command reproduces everything:**

```bash
pip install -r requirements.txt
python run.py --input data/ --output submission.csv
python -m eval.run                     # every number in the report
```

Test this from a **clean clone into a fresh venv** before submitting. A dependency you installed three days ago and forgot is the classic way to fail a grader's run.

**R3 — Readable structure.** The layout in `00-MASTER.md` §7. A reviewer should find the detector without hunting. No stray notebooks, no `test2_final_v3.py`, no commented-out blocks.

**R4 — Docstrings everywhere public.** What it does, what it takes, what it returns, and *why* where the why is non-obvious. The brute-force justification in Phase 5 is exactly the kind of comment that earns credit: it shows the choice was reasoned, not naive.

**R5 — Tests that exist and pass.** `pytest` green from clean clone. Put the pass count in the README.

**R6 — `docs/DECISIONS.md`.** Every non-obvious choice with its rationale and what it costs if wrong. No LLM in the detection path. Brute force over a solver. Abstain over guess. Cap at N. This file is where an AI reviewer finds evidence of judgement rather than luck.

**R7 — Deterministic.** Same input, same output. Seed anything random. Add a test that runs the pipeline twice and diffs the output. State it in the README — reproducibility is a claim most teams cannot make.

**R8 — No secrets, no absolute paths, no network at runtime.** Add a CI-style check script that greps for `C:\`, `/Users/`, API-key patterns and `requests.get`.

**R9 — Zip hygiene.** No `.venv`, no `__pycache__`, no `.git` (unless asked), no datasets you were not told to include. Keep it under whatever limit they set and state the size in the README.

---

## Deliverables

- [ ] `README.md` per R1, with the results table in it
- [ ] `requirements.txt`, pinned
- [ ] `docs/DECISIONS.md`
- [ ] `docs/architecture.md` + one diagram
- [ ] `tools/check_submission.py` — clean-clone run, determinism diff, path and secret grep, zip size
- [ ] `make_submission.sh` — builds the zip with exclusions

## Acceptance

- A fresh venv, clean clone, three commands, and it runs.
- `tools/check_submission.py` passes every check.
- Running the pipeline twice produces byte-identical output.
- The README's first screen answers all five questions.

## Claude Code prompt

```
Build Phase 8 per 08-submission-packaging.md.

1. README.md whose first screen answers: what is this, how to run it, what it outputs, the
   headline results (as a table, inline, not linked), and known limitations. Then architecture
   with one diagram, the method, and a document index.
2. requirements.txt with pinned versions. Verify from a fresh venv.
3. docs/DECISIONS.md: every non-obvious choice, its rationale, and what it costs if wrong.
   Include at minimum: no LLM in the detection path, brute force over a solver, abstain over
   guess, the alert cap value, the severity modulator policy.
4. docs/architecture.md with one diagram. Do not produce multiple overlapping diagrams.
5. tools/check_submission.py asserting: clean-clone run succeeds, two runs produce byte-
   identical output, no absolute paths (C:\, /Users/, /home/), no API-key patterns, no runtime
   network calls (grep for requests, urllib, httpx in src/), zip size under the stated limit.
6. make_submission.sh building the zip, excluding .venv, __pycache__, .pytest_cache, data/ and
   any file over 5MB unless explicitly allowed.
7. Add a test that runs the full pipeline twice and diffs the output.

Every public function in the codebase must have a docstring before this phase is done. Audit
and fill any that are missing - an AI reviewer reads this code.
```
