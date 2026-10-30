"""Checks a submission folder's format with the organisers' own validators, before anything ships.

    python run.py --split test --out submission
    python -m eval.validate_submission submission

The test labels are hidden, so the test submission cannot be scored. It can be validated: this
runs ``validate_predictions`` and ``validate_resolution`` from the pack's ``evaluate.py``
unmodified (the checks that make the scorer exit 2), then checks what they cannot: every test
patient has resolution rows, every written line of every test patient has one, and no line has
two. The patients and lines are counted from the raw file with this module's own split, not
through the pipeline's adapter, so a patient the adapter dropped would show up as missing.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

from eval.pack import data_dir, official_scorer, require_pack
from medsafe.data.adapter import COLUMN_MAP, find_input, read_table
from medsafe.output.writer import PREDICTIONS_FILE, RESOLUTION_FILE, token_key

TOKEN_SPLIT = re.compile(r"[;\r\n]")      # the pack's definition of a written token


def raw_tokens(split: str, input_dir: Path | None = None) -> dict[str, set[str]]:
    """Patient id (upper case) -> its written tokens (token_key), read straight from the file in
    ``input_dir`` (default: the pack)."""
    columns = COLUMN_MAP["patients"]
    table = read_table(find_input(input_dir or data_dir(), "patients", split))
    found: dict[str, set[str]] = {}
    for record in table.records:
        patient_id = str(record.get(columns["patient_id"]) or "").strip().upper()
        listed = record.get(columns["medications"]) or ""
        tokens = listed if isinstance(listed, list) else TOKEN_SPLIT.split(str(listed))
        found.setdefault(patient_id, set()).update(token_key(t) for t in tokens if str(t).strip())
    return found


def load_official():
    """The pack's evaluate.py as a module, unmodified."""
    spec = importlib.util.spec_from_file_location("official_evaluate", official_scorer())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(folder: Path, split: str = "test") -> list[str]:
    """Problems with a submission folder; empty if it is valid. The official validators exit the
    process on a format error, exactly as the scorer would."""
    official = load_official()
    predictions = official.validate_predictions(official.read_csv(folder / PREDICTIONS_FILE, "predictions"))
    resolution = official.validate_resolution(official.read_csv(folder / RESOLUTION_FILE, "resolution"))
    tokens = raw_tokens(split)
    problems = []
    unknown = set(predictions.patient_id) - set(tokens)
    if unknown:
        problems.append(f"{len(unknown)} prediction rows name unknown patients")
    keys = list(zip(resolution.patient_id, resolution.tok))
    have = set(keys)
    duplicates = [k for k, n in Counter(keys).items() if n > 1]
    if duplicates:
        problems.append(f"{len(duplicates)} written lines have more than one row, e.g. {duplicates[:3]}")
    missing = [(p, t) for p, ts in tokens.items() for t in ts if (p, t) not in have]
    if missing:
        problems.append(f"{len(missing)} written lines have no resolution row, e.g. {missing[:3]}")
    uncovered = [p for p in tokens if not any((p, t) in have for t in tokens[p])]
    if uncovered:
        problems.append(f"{len(uncovered)} patients have no resolution row, e.g. {uncovered[:3]}")
    covered = len(tokens) - len(uncovered)
    print(f"{len(predictions)} alerts, {len(resolution)} resolution rows; {split} file: "
          f"{len(tokens)} patients, {sum(map(len, tokens.values()))} distinct written lines; "
          f"patients covered {covered}/{len(tokens)}, lines covered "
          f"{sum(map(len, tokens.values())) - len(missing)}; duplicate rows {len(duplicates)}; "
          f"official validators passed")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns 0 if valid, 1 if not, 2 on an official format error."""
    parser = argparse.ArgumentParser(description="Validate a submission folder.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--split", choices=("train", "test"), default="test")
    args = parser.parse_args(argv)
    require_pack()
    problems = validate(args.folder, args.split)
    for problem in problems:
        print(f"INVALID: {problem}")
    print("valid" if not problems else "not valid")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
