"""A patient with an unreadable value is kept, run through the pipeline, and flagged in the output.

docs/DECISIONS.md D-001: dropping a patient misses every issue they have, so a bad clinical
value degrades that one field to None and the record says so.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

from medsafe.data.adapter import load_dataset
from medsafe.explain.data_quality import UNREADABLE_NOTES, data_quality_notes
from medsafe.pipeline import BUILT_STAGES, Settings, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
INPUT_FILES = ("patients.csv", "drugs.csv", "interactions.csv")


def input_with_bad_weight(tmp_path: Path, patient_id: str = "P0042") -> Path:
    """A copy of the fixture input in which one patient's weight reads 'seventy'."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for name in INPUT_FILES[1:]:
        shutil.copy2(FIXTURES_DIR / name, input_dir / name)
    with (FIXTURES_DIR / "patients.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    weight = rows[0].index("weight_kg")
    for row in rows[1:]:
        if row[0] == patient_id:
            row[weight] = "seventy"
    with (input_dir / "patients.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    return input_dir


def test_unreadable_weight_patient_is_loaded_checked_and_noted(tmp_path: Path) -> None:
    input_dir = input_with_bad_weight(tmp_path)
    dataset = load_dataset(input_dir)
    clean = {p.patient_id: p for p in load_dataset(FIXTURES_DIR).patients}

    # Loads: kept, weight None, everything else as written.
    patient = next(p for p in dataset.patients if p.patient_id == "P0042")
    assert patient.weight_kg is None and patient.unreadable_fields == ("weight_kg",)
    assert patient.medications == clean["P0042"].medications
    assert patient.egfr == clean["P0042"].egfr

    # Checked: it reaches every built stage of the pipeline with its full medication list.
    result = run_pipeline(dataset, Settings())
    entry = next(r for r in result.patients if r.patient.patient_id == "P0042")
    assert result.stages_built == BUILT_STAGES
    assert entry.patient.medications == clean["P0042"].medications
    assert entry.notes == (UNREADABLE_NOTES["weight_kg"],)

    # Output: every medication row is written, each carrying the note; the run reports it.
    output = tmp_path / "out.csv"
    completed = subprocess.run([sys.executable, "run.py", "--input", str(input_dir),
                                "--output", str(output)], cwd=REPO_ROOT, check=True,
                               capture_output=True, text=True)
    with output.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["patient_id"] == "P0042"]
    assert [row["raw"] for row in rows] == [m.raw for m in clean["P0042"].medications]
    assert all(row["patient_notes"] == UNREADABLE_NOTES["weight_kg"] for row in rows)
    assert "200 loaded (199 clean, 1 degraded), 0 skipped" in completed.stdout
    assert "degraded bad_type:weight_kg: 1" in completed.stdout


def test_egfr_note_wording_matches_the_decision() -> None:
    assert UNREADABLE_NOTES["egfr"] == ("eGFR could not be read; renal checks not verifiable "
                                        "for this patient.")


def test_clean_patients_carry_no_notes() -> None:
    dataset = load_dataset(FIXTURES_DIR)
    assert all(data_quality_notes(p) == () for p in dataset.patients)
