"""One malformed patient never stops the run, and every written line still gets a row (D-028)."""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import MINI_DIR, REPO_ROOT
from eval.validate_submission import raw_tokens
from medsafe import pipeline
from medsafe.data.adapter import Dataset
from medsafe.output.writer import token_key, write_resolution
from medsafe.pipeline import Settings, build_resolver, run_pipeline


def resolution_keys(path: Path) -> list[tuple[str, str]]:
    """(patient_id upper, token_key) for every row of a resolution file."""
    with path.open(newline="", encoding="utf-8") as handle:
        return [(r["patient_id"].upper(), token_key(r["written_token"])) for r in csv.DictReader(handle)]


def test_a_patient_whose_rules_fail_gets_no_alerts_and_keeps_its_lines(
        mini: Dataset, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    normal = {p.patient.patient_id: p.alerts for p in run_pipeline(mini).patients}
    real = pipeline.run_rules

    def broken(patient, resolutions, tables):
        """run_rules, failing for one patient."""
        if patient.patient_id == "H4P-MINI0001":
            raise KeyError("a field no rule expected")
        return real(patient, resolutions, tables)

    monkeypatch.setattr(pipeline, "run_rules", broken)
    result = run_pipeline(mini)
    by_id = {p.patient.patient_id: p for p in result.patients}
    assert [(f.patient_id, f.stage) for f in result.failures] == [("H4P-MINI0001", "rules")]
    assert by_id["H4P-MINI0001"].alerts == () and by_id["H4P-MINI0001"].rules is None
    assert normal["H4P-MINI0001"]                      # it did have alerts; they are withheld
    assert {i: p.alerts for i, p in by_id.items() if i != "H4P-MINI0001"} == \
        {i: a for i, a in normal.items() if i != "H4P-MINI0001"}
    write_resolution(result, tmp_path / "r.csv")
    written = set(resolution_keys(tmp_path / "r.csv"))
    assert all(("H4P-MINI0001", token_key(m.raw)) in written for m in by_id["H4P-MINI0001"].patient.medications)


def test_a_line_the_resolver_cannot_process_is_abstained_not_dropped(mini: Dataset) -> None:
    resolver = build_resolver(mini, Settings())
    real = resolver.resolve
    target = mini.patients[0].medications[0].raw
    resolver.resolve = lambda raw: (_ for _ in ()).throw(ValueError("odd bytes")) if raw == target else real(raw)
    result = run_pipeline(mini, Settings(), resolver)
    first = result.patients[0].resolutions[0]
    assert first.method == "abstained" and first.abstain_reason == "error" and first.verify_manually
    assert [(f.stage, f.line) for f in result.failures] == [("resolve", target)]
    assert len(result.patients) == len(mini.patients)


MALFORMED = [
    # patient_id, age, sex, weight_kg, egfr, pregnant, diagnoses, allergies, medications, prescribers
    ["H4P-BAD00001", "abc", "X", "", "-5", "maybe", "EF 0.%; ; ;;", "", "Tab Dolo 650 SOS; ; ;", "two"],
    ["H4P-BAD00002", "70", "M", "60", "45", "NA", "?" * 3000, "penicillin?!", "???;12345;" + "x" * 5000, "1"],
    ["H4P-BAD00003", "55", "F", "55", "abc", "Y", "HTN", "NKDA", "Tab​Glycomet 500 BD;Tab Glycomet 500 BD", "1"],
    ["H4P-BAD00001", "40", "F", "50", "90", "N", "", "", "Tab Pan 40 OD", "1"],          # duplicate id
    ["H4P-BAD00004", "40", "F", "50", "90", "N", "", "", "", "1"],                       # no medicines
    ["", "40", "F", "50", "90", "N", "", "", "Tab Pan 40 OD", "1"],                      # no id
    ["H4P-BAD00005", "40", "F", "50", "90", "N", "DM", "", "Tab Pan 40 OD", "1", "extra", "cells"],
]


def test_malformed_patients_never_crash_a_run_and_every_line_is_written(tmp_path: Path) -> None:
    folder = tmp_path / "pack"
    shutil.copytree(MINI_DIR, folder)
    with (folder / "patients_test.csv").open("a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(MALFORMED)
    run = subprocess.run([sys.executable, str(REPO_ROOT / "run.py"), "--input", str(folder),
                          "--split", "test", "--out", str(tmp_path / "out")],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "failures contained: 0" in run.stdout
    keys = resolution_keys(tmp_path / "out" / "H4_resolution.csv")
    assert len(keys) == len(set(keys))                                  # no duplicate rows
    raw = raw_tokens("test", folder)
    written = set(keys)
    for patient_id in ("H4P-MINIT001", "H4P-MINIT002", "H4P-BAD00001", "H4P-BAD00002",
                       "H4P-BAD00003", "H4P-BAD00005"):
        assert {t for p, t in written if p == patient_id}, patient_id
    assert {t for p, t in written if p == "H4P-BAD00002"} == raw["H4P-BAD00002"]
    # The first row of a repeated id is kept, so only its lines are written.
    assert {t for p, t in written if p == "H4P-BAD00001"} == {token_key("Tab Dolo 650 SOS")}
    assert not {t for p, t in written if p == "H4P-BAD00004"}           # nothing to write
