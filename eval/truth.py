"""Ground truth the harness scores against. The only module that knows the label file layout.

Fixtures: ``expected_issues.csv`` and ``ground_truth.csv`` beside the input files, written by
``tools/make_fixtures.py``. When the real labels arrive, change this module and nothing else.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from eval.records import Issue, TruthMedication

ISSUES_FILE = "expected_issues.csv"
MEDICATIONS_FILE = "ground_truth.csv"
LIST_SEPARATOR = "|"


@dataclass(frozen=True)
class Truth:
    """Every true issue, and what every medication line really is."""

    issues: tuple[Issue, ...]
    medications: tuple[TruthMedication, ...]


def _read(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into rows."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _split(cell: str) -> tuple[str, ...]:
    """Split a separator-joined cell into its non-empty items."""
    return tuple(item for item in cell.split(LIST_SEPARATOR) if item)


def load_truth(input_dir: str | Path) -> Truth | None:
    """Load the labels that sit beside an input directory's data files.

    Args:
        input_dir: The directory passed to ``run.py --input``.

    Returns:
        The labels, or None if the directory has no issue labels (recall cannot be measured).
    """
    input_dir = Path(input_dir)
    if not (input_dir / ISSUES_FILE).is_file():
        return None
    issues = tuple(
        Issue(patient_id=row["patient_id"], issue_type=row["issue_type"],
              drugs=frozenset(_split(row["drugs"])), severity=row["severity"],
              rule_id=row["rule_id"], near_miss=row["near_miss"] == "Y",
              near_miss_reason=row["near_miss_reason"], raw_drugs=_split(row["raw_drugs"]))
        for row in _read(input_dir / ISSUES_FILE))
    medications_path = input_dir / MEDICATIONS_FILE
    medications = tuple(
        TruthMedication(patient_id=row["patient_id"], med_index=int(row["med_index"]),
                        raw=row["raw"], generic=row["true_generic"] or None,
                        mangling=tuple(row["mangling"].split("+")))
        for row in (_read(medications_path) if medications_path.is_file() else ()))
    return Truth(issues=issues, medications=medications)
