"""A patient with an unreadable value is kept, run through every built stage, and flagged in the
output (docs/DECISIONS.md D-001): dropping a patient misses every issue they have."""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import MINI_DIR, REPO_ROOT
from medsafe.data.adapter import load_dataset
from medsafe.explain.data_quality import UNREADABLE_NOTES, data_quality_notes
from medsafe.pipeline import BUILT_STAGES, Settings, run_pipeline


def mini_with_bad_weight(tmp_path: Path) -> Path:
    """A copy of the mini fixtures in which H4P-MINI0001's weight reads 'seventy'."""
    folder = tmp_path / "mini"
    shutil.copytree(MINI_DIR, folder)
    path = folder / "patients_train.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(",F,61.5,", ",F,seventy,", 1),
                    encoding="utf-8")
    return folder


def test_unreadable_weight_patient_is_loaded_checked_and_noted(tmp_path: Path) -> None:
    folder = mini_with_bad_weight(tmp_path)
    clean = {p.patient_id: p for p in load_dataset(MINI_DIR, "train").patients}
    dataset = load_dataset(folder, "train")

    # Loads: kept, weight None, everything else as written.
    patient = dataset.patients[0]
    assert patient.patient_id == "H4P-MINI0001"
    assert patient.weight_kg is None and patient.unreadable_fields == ("weight_kg",)
    assert patient.medications == clean["H4P-MINI0001"].medications
    assert patient.egfr == clean["H4P-MINI0001"].egfr

    # Checked: every built stage runs on it; every line is resolved.
    result = run_pipeline(dataset, Settings())
    entry = result.patients[0]
    assert result.stages_built == BUILT_STAGES and "resolve" in BUILT_STAGES
    assert [r.generics for r in entry.resolutions] == [
        ("glimepiride", "metformin"), ("paracetamol",), ("paracetamol",), ("amlodipine", "telmisartan")]
    assert entry.notes == (UNREADABLE_NOTES["weight_kg"],)

    # Output: every line is written, each carrying the note; the run reports the degradation.
    out = tmp_path / "out"
    completed = subprocess.run([sys.executable, "run.py", "--input", str(folder), "--split", "train",
                                "--output", str(out)], cwd=REPO_ROOT, check=True,
                               capture_output=True, text=True)
    with (out / "H4_resolution.csv").open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["patient_id"] == "H4P-MINI0001"]
    assert [r["written_token"] for r in rows] == [m.raw for m in patient.medications]
    assert all(r["patient_notes"] == UNREADABLE_NOTES["weight_kg"] for r in rows)
    assert "6 loaded (5 clean, 1 degraded), 0 skipped" in completed.stdout
    assert "degraded bad_type:weight_kg: 1" in completed.stdout


def test_egfr_note_wording_matches_the_decision() -> None:
    assert UNREADABLE_NOTES["egfr"] == "eGFR could not be read; renal checks not verifiable for this patient."


def test_clean_patients_carry_no_notes(mini) -> None:
    assert all(data_quality_notes(p) == () for p in mini.patients)
