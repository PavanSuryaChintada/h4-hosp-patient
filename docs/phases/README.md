# H4 Medication Safety — Round 2 phase pack

Eleven documents. Each is self-contained and ends with a copy-paste Claude Code prompt.

## How to use

1. Read `00-MASTER.md`. It has the stack, the build order, and a **standing context block** to paste at the top of every session.
2. One phase per session. Paste the context block, then that phase's prompt.
3. Work in build order, not numeric order. **Phase 1, then Phase 7, then the rest.**

## Order

| Order | Phase | Why here |
|---|---|---|
| 1 | 01 Data contract & adapter | Everything depends on it, and it works before the dataset arrives |
| 2 | **07 Evaluation harness** | You cannot tune what you cannot measure |
| 3 | 02 Name resolution | The brief calls it most of the difficulty |
| 4 | 03 Rule engine | |
| 5 | 04 Context severity | Where most teams lose |
| 6 | 05 Alert graph collapse | The differentiator |
| 7 | 06 Budget & output contract | Wrong format = zero |
| 8 | 08 Submission packaging | An AI reads the zip |
| 9 | 10 Report & limitations | Never cut |
| 10 | 09 UI | Cuttable |

## The three things that decide this

1. **Both numbers move the right way at once** — serious recall up, low-severity volume down. Either alone is trivial and meaningless.
2. **Name resolution works**, because an unresolved drug is a silent miss that shows up nowhere except your recall.
3. **The repo reads well**, because a model is grading it. README, structure, docstrings, one-command repro, honest limitations.

## When the dataset arrives

Change `COLUMN_MAP` in `src/medsafe/data/adapter.py`. Run `tests/test_adapter.py` against the real files. If it passes, the pipeline works. That is the whole point of Phase 1.

Then replace `eval/mirror.py` with the real `evaluate.py` logic and re-run `eval/sweep.py` to retune the thresholds against the actual penalty curve.
