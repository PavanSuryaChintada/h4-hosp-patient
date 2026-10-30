"""Ground truth from the pack: train_labels.csv and train_resolution.csv.

The only module in eval/ that knows the label file layout. The pipeline (src/medsafe/) never
reads these files; tests/test_guards.py enforces it.
"""

from __future__ import annotations

import csv
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from eval.records import Issue, TruthToken

LABELS_FILE = "train_labels.csv"
RESOLUTION_FILE = "train_resolution.csv"
SEPARATOR = ";"


@dataclass(frozen=True)
class Truth:
    """Every true issue and every true resolution, for some set of training patients."""

    issues: tuple[Issue, ...]
    tokens: tuple[TruthToken, ...]


def _rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into rows of strings."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _drugs(cell: str) -> frozenset[str]:
    """A ';'-separated generic list as a set, lowercased and trimmed."""
    return frozenset(part.strip().lower() for part in cell.split(SEPARATOR) if part.strip())


def load_truth(data_dir: Path, patient_ids: Collection[str] | None = None) -> Truth:
    """Load the training labels and resolutions, optionally for some patients only.

    Args:
        data_dir: The pack's data folder.
        patient_ids: Keep only these patients; all when None.
    """
    keep = (lambda pid: True) if patient_ids is None else (lambda pid: pid in patient_ids)
    issues = tuple(Issue(row["patient_id"], row["issue_type"], _drugs(row["drugs_involved"]),
                         row["severity"], row["near_miss"] == "1", row["suggested_action"])
                   for row in _rows(data_dir / LABELS_FILE) if keep(row["patient_id"]))
    tokens = tuple(TruthToken(row["patient_id"], row["written_token"],
                              _drugs(row["resolved_generic"]), row["token_kind"])
                   for row in _rows(data_dir / RESOLUTION_FILE) if keep(row["patient_id"]))
    return Truth(issues, tokens)


def write_truth_subset(data_dir: Path, patient_ids: Collection[str], out_dir: Path) -> tuple[Path, Path]:
    """Copy the truth rows of some patients, unchanged, for the official scorer.

    Returns:
        Paths of the labels and resolution files written. Named ``*_labels.csv`` and
        ``*_resolution.csv`` as the scorer expects.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in (LABELS_FILE, RESOLUTION_FILE):
        with (data_dir / name).open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            target_path = out_dir / name
            with target_path.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=reader.fieldnames, lineterminator="\n")
                writer.writeheader()
                writer.writerows(row for row in reader if row["patient_id"] in patient_ids)
        written.append(target_path)
    return written[0], written[1]
