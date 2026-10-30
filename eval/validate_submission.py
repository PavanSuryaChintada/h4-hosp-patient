"""Checks a submission folder's format with the organisers' own validators, before anything ships.

    python run.py --split test --out submission
    python -m eval.validate_submission submission

The test labels are hidden, so the test submission cannot be scored. It can be validated: this
runs ``validate_predictions`` and ``validate_resolution`` from the pack's ``evaluate.py``
unmodified (the checks that make the scorer exit 2), then checks what they cannot: every test
patient has resolution rows, and every written line of every test patient has one.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from eval.pack import data_dir, official_scorer, require_pack
from medsafe.data.adapter import load_dataset
from medsafe.output.writer import PREDICTIONS_FILE, RESOLUTION_FILE, token_key


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
    patients = load_dataset(data_dir(), split).patients
    problems = []
    ids = {p.patient_id.upper() for p in patients}
    unknown = set(predictions.patient_id) - ids
    if unknown:
        problems.append(f"{len(unknown)} prediction rows name unknown patients")
    have = set(zip(resolution.patient_id, resolution.tok))
    missing = [(p.patient_id, m.raw) for p in patients for m in p.medications
               if (p.patient_id.upper(), token_key(m.raw)) not in have]
    if missing:
        problems.append(f"{len(missing)} written lines have no resolution row, e.g. {missing[:3]}")
    print(f"{len(predictions)} alerts, {len(resolution)} resolution rows, {len(patients)} {split} "
          f"patients; official validators passed")
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
