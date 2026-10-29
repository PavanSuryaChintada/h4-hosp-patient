# 00 — Master Brief
## H4 Medication Safety — Round 2 build

Read this first. Paste its context block at the top of every Claude Code session.

---

## 1. What changed from Round 1

| Round 1 | Round 2 |
|---|---|
| Frontend demo, hardcoded JSON | Real pipeline over 5,000 supplied patients |
| Looked right | Must *score* right against `evaluate.py` |
| Judged by humans watching a video | Judged by an AI reading the code zip, plus a score |

The UI spec and design system from Round 1 survive unchanged. Everything behind them is replaced.

---

## 2. The two numbers that decide this

The brief states it plainly: **recall on serious issues**, and **a penalty for low-severity alert volume**.

```
score ≈ f(recall on serious issues) − g(low-severity alert count)
```

A system that flags everything scores near zero. A system that flags nothing scores zero. **The entire engineering problem is finding the ridge between them, and proving you found it deliberately rather than by luck.**

Everything in these phases serves that. If a task does not move recall up or low-severity volume down, it is decoration.

---

## 3. The evaluator is an AI reading your code

This is the under-exploited scoring surface. Assume a model opens the zip and forms a judgement from:

- `README.md` — does it explain what this is and how to run it, in sixty seconds?
- Directory structure — can it find the detector without hunting?
- Function and module names — do they say what they do?
- Docstrings on every public function — what it does, what it takes, what it returns
- One command that reproduces every number in your report
- Tests that exist and pass
- A limitations section that names real weaknesses

**Budget real time for this.** A technically identical submission with a clear README and a one-command repro will outscore a messy one, every time. Phase 8 covers it.

---

## 4. Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | The evaluator is `evaluate.py`; stay in its world |
| Core | Pure stdlib + `pandas` for IO | Every extra dependency is a thing that can fail on the grader's machine |
| Fuzzy matching | `rapidfuzz` | Fast, pip-installable, no model weights |
| Graph solve | Brute force over subsets | n < 12 per patient; exact, instant, no solver dependency |
| Tests | `pytest` | Expected |
| UI | Vite + React + TS (Round 1 spec unchanged) | Separate folder, never on the scoring path |
| LLM | **None in the scoring path** | See below |

### No LLM in the detection path

Deliberate, and state it in the report. Three reasons:

1. The rules are deterministic and auditable. A clinician can trace every alert to a table row.
2. Reproducibility — the same input gives the same output on the grader's machine, every run.
3. No API key, no network, no model download. The zip runs offline.

If you want an LLM anywhere, put it in the *explanation* layer only — turning a structured alert into prose — and make the system work identically with it removed.

---

## 5. Build order

| Phase | What | Time | Blocking? |
|---|---|---|---|
| 1 | Data contract + adapter + fixtures | 3h | Yes — everything depends on it |
| 7 | Evaluation harness *(build early, not last)* | 2h | Yes — you tune against it |
| 2 | Name resolution | 4h | Yes — unresolved name = missed issue |
| 3 | Rule engine | 3h | Yes |
| 4 | Context severity | 2h | Yes |
| 5 | Alert graph collapse | 3h | The differentiator |
| 6 | Alert budget + output contract | 2h | Yes |
| 8 | Submission packaging | 3h | Yes |
| 9 | UI on real data | 4h | Cuttable |
| 10 | Report + limitations | 2h | Yes |

**Phase 7 before Phase 2.** You cannot tune a detector you cannot measure. Teams that build the harness last discover their recall problem on the final night.

**Cut order if short:** Phase 9 UI → graph collapse visualisation (keep the logic) → prose explanation layer. **Never cut** Phase 7, 8 or 10.

---

## 6. Standing context block

Paste at the top of every session:

```
PROJECT: H4 Medication Safety — flags drug safety risks from a patient's medication list.
Round 2: scored by evaluate.py on 5,000 supplied patients, plus an AI reviewer reading the repo.

SCORING REALITY
- Recall on serious issues goes UP. Low-severity alert volume goes DOWN. Both are scored.
- A system that flags everything scores near zero. This is the central design constraint.
- Recall on 300 seeded near-misses is reported prominently.

NON-NEGOTIABLE RULES
1. No LLM in the detection path. Deterministic rules only. Same input, same output, every run.
2. No network calls at runtime. The zip runs offline on the grader's machine.
3. Every alert carries its reasons — the rule id, the drugs, the patient values that triggered it.
   An alert without traceable reasons is a bug.
4. Never claim a patient is safe. Only that no issue was found in what was seen.
5. Name resolution abstains rather than guessing. A confident wrong resolution is worse than a miss.
6. Every number in the report comes from a committed script, re-runnable with one command.
7. Every public function has a docstring. An AI reads this code.

Ask me before inventing a requirement that is not in the spec I give you.
```

---

## 7. Repo layout

```
/src/medsafe
  data/        loaders, adapter, schema validation
  resolve/     brand→generic resolution
  rules/       interaction, duplicate, renal, contraindication
  severity/    patient-context re-scoring
  collapse/    alert graph + minimal drug set
  budget/      ranking and capping
  output/      the submission format writer
  explain/     plain-English reason text
/eval          our mirror of the scoring, plus near-miss tracking
/tests
/tools         one-off scripts, fixture generation
/ui            Round 1 React app, never on the scoring path
/docs          report, limitations, decisions
README.md
run.py         one entry point: python run.py --input <dir> --output <file>
```

One entry point. If the grader has to read three files to work out how to run it, that is a lost point.

---

## 8. Open questions — answer before Phase 1 locks

1. **Is `evaluate.py` supplied, or does an AI grade the code?** If supplied, read it line by line before writing anything — its exact penalty shape decides your alert cap.
2. **What is the required output format?** If your output does not parse, the score is zero regardless of how good the detector is.
3. **Deadline, and what is due** — code, report, video, or all three?
4. **Is an LLM permitted?** The plan assumes none in the scoring path either way.
