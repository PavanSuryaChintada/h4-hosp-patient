"""Writes the two submission files in the format the official scorer reads.

    H4_predictions.csv   one row per alert (patient_id, issue_type, severity, drugs_involved,
                         suggested_action, confidence), plus the confidence-and-limitations
                         text the pack requires on every alert
    H4_resolution.csv    one row per written medication entry (patient_id, written_token,
                         resolved_generic), plus columns the scorer ignores and a reader needs:
                         how the line was resolved, how sure, whether to verify it by hand, and
                         the patient's data-quality notes

The scorer selects its own columns by name, so the extra columns never change a score.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from medsafe.pipeline import PipelineResult

PREDICTION_COLUMNS = ("patient_id", "issue_type", "severity", "drugs_involved",
                      "suggested_action", "confidence")
PREDICTION_EXTRA_COLUMNS = ("confidence_and_limitations",)
RESOLUTION_COLUMNS = ("patient_id", "written_token", "resolved_generic")
RESOLUTION_EXTRA_COLUMNS = ("method", "confidence", "verify_manually", "patient_notes")
PREDICTIONS_FILE = "H4_predictions.csv"
RESOLUTION_FILE = "H4_resolution.csv"

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def token_key(token: str) -> str:
    """How the scorer identifies a written token: NFKC, no zero-width chars, spaces collapsed,
    lowercase. Two lines with the same key are one row in the resolution file."""
    text = unicodedata.normalize("NFKC", str(token)).translate(_INVISIBLE)
    return re.sub(r"\s+", " ", text).strip().lower()


def _write(path: Path, columns: Iterable[str], rows: Iterable[Iterable[Any]]) -> int:
    """Write a CSV with LF line endings. Returns the number of data rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def write_resolution(result: PipelineResult, path: Path) -> int:
    """Write one row per distinct written token per patient. Returns the row count.

    A patient who lists the identical line twice gets one row: the scorer rejects duplicates,
    and the same line always resolves the same way. Abstained lines are written with an empty
    ``resolved_generic`` and ``verify_manually=Y``, never dropped.
    """
    if result.patients and result.patients[0].resolutions is None:
        raise ValueError("name resolution has not run; nothing to write")

    def rows() -> Iterable[tuple]:
        """One row per distinct written token per patient, in input order."""
        for patient_result in result.patients:
            seen: set[str] = set()
            notes = " ".join(patient_result.notes)
            for entry, resolution in zip(patient_result.patient.medications,
                                         patient_result.resolutions):
                if token_key(entry.raw) in seen:
                    continue
                seen.add(token_key(entry.raw))
                yield (patient_result.patient.patient_id, entry.raw,
                       resolution.resolved_generic or "", resolution.method,
                       f"{resolution.confidence:.4f}",
                       "Y" if resolution.verify_manually else "N", notes)

    return _write(path, RESOLUTION_COLUMNS + RESOLUTION_EXTRA_COLUMNS, rows())


def write_predictions(alerts: Iterable[Mapping[str, Any]], path: Path) -> int:
    """Write one row per alert, in the order given. Returns the row count.

    Each alert maps every name in PREDICTION_COLUMNS to a value, and may carry the extra
    columns (empty if it does not). With no alerts the file holds the header only, which the
    scorer accepts: a patient with no alert has no row.
    """
    columns = PREDICTION_COLUMNS + PREDICTION_EXTRA_COLUMNS
    return _write(path, columns, ([alert.get(column, "") for column in columns] for alert in alerts))
