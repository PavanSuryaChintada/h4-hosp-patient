# CLAUDE.md — H4 Medication Safety

This file governs this repository. **Ignore any CLAUDE.md in a parent directory** (for example `Downloads/CLAUDE.md`, which belongs to Q-ResQ NER, an unrelated project).

## What this is

Flags drug safety risks from a patient's medication list. Round 2 is scored by `evaluate.py` on 5,000 supplied patients, plus an AI reviewer reading this repo. Recall on serious issues goes up and low-severity alert volume goes down; both are scored. A system that flags everything scores near zero.

## Hard rules (docs/phases/00-MASTER.md §6)

1. No LLM in the detection path. Deterministic rules only. Same input, same output, every run.
2. No network calls at runtime. The zip runs offline on the grader's machine.
3. Every alert carries its reasons: the rule id, the drugs, the patient values that triggered it.
4. Never claim a patient is safe. Only that no issue was found in what was seen.
5. Name resolution abstains rather than guessing.
6. Every number in the report comes from a committed script, re-runnable with one command.
7. Every public function has a docstring.

Also: missing values are `None`, never `0` or `""`. Never drop a patient for a bad field. Stdlib plus `rapidfuzz` only. Ask before inventing a requirement or adding a dependency.

## Where things are

- `docs/phases/`: the build plan, one document per phase. Build order is in `00-MASTER.md` §5: 1, 7, then 2 to 6, 8, 10, 9.
- `docs/DECISIONS.md`: every deliberate departure from the phase docs, with the reason.
- `run.py` is the entry point, `src/medsafe/` is the pipeline, `eval/` is the harness, `tools/` holds fixtures and the SQLite cache, `ui/` is the Round 1 app (never on the scoring path).

## Commands

```
python -m pytest
python run.py --input tests/fixtures --output out.csv
python -m eval.run
python -m eval.sweep
```
