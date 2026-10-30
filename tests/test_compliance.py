"""The pack's mandatory outputs, and the wall between the two tracks.

M1  every alert has a non-empty suggested action, the table's word for word
M2  every alert has confidence-and-limitations text naming the rule and what was not checked
M3  every alert and every patient summary says a clinician decides
M4  no output ever calls a patient safe (UI strings: tests/test_ui_copy.py)
and Track A's files are byte-identical with the clinician-only layer present or absent.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import MINI_DIR, REPO_ROOT, requires_pack
from medsafe.data.adapter import Dataset
from medsafe.explain import limitations
from medsafe.explain.limitations import DISCLAIMER, patient_summary
from medsafe.pipeline import run_pipeline

SAFE = re.compile(r"\bsafe\b", re.IGNORECASE)
OUTPUT_FILES = ("H4_predictions.csv", "H4_resolution.csv")
CLINICIAN_ONLY = ("src/medsafe/workflow.py", "src/medsafe/explain/prioritise.py")


def run_track_a(root: Path, out: Path, split: str = "train") -> None:
    """Run Track A from ``root`` on the mini fixtures, writing to ``out``."""
    subprocess.run([sys.executable, str(root / "run.py"), "--input", str(MINI_DIR), "--split", split,
                    "--out", str(out)], cwd=root, check=True, capture_output=True, text=True)


def check_alerts(rows: list[dict[str, str]], dataset: Dataset) -> None:
    """M1-M3 on predictions rows."""
    table_actions = ({i.action for i in dataset.interactions} | {r.action for r in dataset.renal_rules}
                     | {g.action for g in dataset.duplicate_groups.values()}
                     | {c.action for c in dataset.contraindications})
    for row in rows:
        text = row["confidence_and_limitations"]
        assert row["suggested_action"].strip(), row
        assert (row["suggested_action"] in table_actions
                or "pregnancy_category" in text or "listed in more than one entry" in row["suggested_action"]), row
        assert "Rule " in text and "may be incomplete" in text and DISCLAIMER in text, row


def test_every_alert_carries_action_limitations_and_disclaimer(mini: Dataset, tmp_path: Path) -> None:
    run_track_a(REPO_ROOT, tmp_path)
    with (tmp_path / "H4_predictions.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    check_alerts(rows, mini)


def test_limitations_name_what_could_not_be_checked(mini: Dataset) -> None:
    by_id = {p.patient.patient_id: p for p in run_pipeline(mini).patients}
    gaps = limitations.not_checked(by_id["H4P-MINI0002"].patient, by_id["H4P-MINI0002"].rules.regimen)
    assert any("eGFR not recorded" in g for g in gaps)
    assert not any("pregnancy" in g for g in gaps)            # male: not applicable, not missing
    no_allergy = limitations.not_checked(by_id["H4P-MINI0004"].patient, by_id["H4P-MINI0004"].rules.regimen)
    assert any("allergy" in g for g in no_allergy)


def test_patient_with_no_alert_is_never_called_safe(mini: Dataset) -> None:
    for result in run_pipeline(mini).patients:
        summary = patient_summary(result.patient, result.rules.regimen, len(result.alerts))
        assert not SAFE.search(summary) and DISCLAIMER in summary
        if not result.alerts:
            assert summary.startswith("No issue was found in the")


@pytest.mark.parametrize("split", ["train", "test"])
def test_no_output_says_safe(tmp_path: Path, split: str) -> None:
    run_track_a(REPO_ROOT, tmp_path, split)
    for name in OUTPUT_FILES:
        assert not SAFE.search((tmp_path / name).read_text(encoding="utf-8")), name
    strings = [v for name, v in vars(limitations).items() if isinstance(v, str) and not name.startswith("__")]
    assert strings and not any(SAFE.search(s) for s in strings)


def test_track_a_is_byte_identical_without_the_clinician_layer(tmp_path: Path) -> None:
    """Prioritising, collapsing, acting, escalating and auditing can never change the CSVs: run
    Track A from a copy of the code with that layer and ui/ deleted, and compare bytes."""
    bare = tmp_path / "bare"
    shutil.copytree(REPO_ROOT / "src", bare / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(REPO_ROOT / "run.py", bare / "run.py")
    for relative in CLINICIAN_ONLY:
        (bare / relative).unlink()
    assert not (bare / "ui").exists()
    run_track_a(REPO_ROOT, tmp_path / "full")
    run_track_a(bare, tmp_path / "without")
    for name in OUTPUT_FILES:
        assert (tmp_path / "full" / name).read_bytes() == (tmp_path / "without" / name).read_bytes(), name


@requires_pack
def test_every_training_alert_is_compliant(train_slice: Dataset) -> None:
    rows = [a for p in run_pipeline(train_slice).patients for a in p.alerts]
    assert rows
    check_alerts([{k: str(v) for k, v in row.items()} for row in rows], train_slice)
    assert not any(SAFE.search(str(v)) for row in rows for v in row.values())
