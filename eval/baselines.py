"""Reference submissions, scored by the official scorer on the same patients as the pipeline.

    oracle                     every true issue at its true severity, plus the true resolution
    oracle, no minor           the same through our minor-alert policy (medsafe.output.policy)
    pack baseline              the organisers' baseline/baseline.py: exact-match lookup,
                               interactions only, minor ones included. Our floor
    pack baseline, no minor    the same through our minor-alert policy
    flag nothing               no alerts, plus the true resolution

They check the harness, fix the ceiling, fix the floor, and measure the minor-alert policy on a
perfect detector and on a weak one.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from collections.abc import Collection
from pathlib import Path
from typing import Any

from eval import official
from eval.pack import pack_baseline
from eval.truth import LABELS_FILE, RESOLUTION_FILE
from medsafe.output.policy import submitted
from medsafe.output.writer import (PREDICTION_COLUMNS, RESOLUTION_COLUMNS, token_key,
                                   write_predictions)

REFERENCES = ("oracle", "oracle, no minor", "pack baseline", "pack baseline, no minor",
              "flag nothing")


def _rows(path: Path, patient_ids: Collection[str] | None = None) -> list[dict[str, str]]:
    """Rows of a CSV file, optionally for some patients only."""
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle)
                if patient_ids is None or row["patient_id"] in patient_ids]


def _write_true_resolution(rows: list[dict[str, str]], path: Path) -> None:
    """The true resolution as a submission file, one row per (patient, token)."""
    seen: set[tuple[str, str]] = set()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(RESOLUTION_COLUMNS)
        for row in rows:
            row_key = (row["patient_id"], token_key(row["written_token"]))
            if row_key not in seen:
                seen.add(row_key)
                writer.writerow([row["patient_id"], row["written_token"], row["resolved_generic"]])


def _as_alerts(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Label or prediction rows as alerts in the submission columns."""
    return [{**{c: row.get(c, "") for c in PREDICTION_COLUMNS},
             "suggested_action": row.get("suggested_action") or "Review",
             "confidence": row.get("confidence") or 1.0} for row in rows]


def run_pack_baseline(folder: Path) -> tuple[Path, Path]:
    """Run the organisers' baseline on the training patients. Returns its two files."""
    folder.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run([sys.executable, "-I", str(pack_baseline()), "--split", "train",
                                "--out", str(folder)], capture_output=True, text=True)
    if completed.returncode != 0:
        raise official.OfficialScorerError(completed.stderr.strip())
    return folder / "H4_predictions.csv", folder / "H4_resolution.csv"


def score_references(data_dir: Path, patient_ids: Collection[str], labels: Path,
                     truth_resolution: Path, work_dir: Path) -> dict[str, dict[str, Any]]:
    """Write and score every reference submission. Returns the official report per reference."""
    issues = _rows(data_dir / LABELS_FILE, patient_ids)
    tokens = _rows(data_dir / RESOLUTION_FILE, patient_ids)
    baseline_predictions, baseline_resolution = run_pack_baseline(work_dir / "pack_baseline_run")
    baseline_alerts = _as_alerts(_rows(baseline_predictions, patient_ids))
    alerts = {
        "oracle": _as_alerts(issues),
        "oracle, no minor": submitted(_as_alerts(issues)),
        "pack baseline": baseline_alerts,
        "pack baseline, no minor": submitted(baseline_alerts),
        "flag nothing": [],
    }
    reports = {}
    for name in REFERENCES:
        folder = work_dir / name.replace(", ", "_").replace(" ", "_")
        folder.mkdir(parents=True, exist_ok=True)
        write_predictions(alerts[name], folder / "H4_predictions.csv")
        resolution = folder / "H4_resolution.csv"
        if name.startswith("pack baseline"):
            resolution.write_bytes(baseline_resolution.read_bytes())
        else:
            _write_true_resolution(tokens, resolution)
        reports[name] = official.score(folder / "H4_predictions.csv", resolution, labels,
                                       truth_resolution, folder / "score.json")
    return reports
