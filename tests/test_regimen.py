"""R1/R2: the regimen is not the resolution. Stopped medicines and non-medicine lines resolve, and
are left out of every check."""

from __future__ import annotations

import csv
import re

import pytest

from conftest import requires_pack
from eval.pack import data_dir
from medsafe.data.adapter import Dataset
from medsafe.data.schema import MedicationEntry, Patient
from medsafe.pipeline import run_pipeline
from medsafe.resolve.resolver import Resolution
from medsafe.rules.regimen import build_regimen, is_stopped


@pytest.mark.parametrize(("raw", "stopped"), [
    ("tab Glycomet 500 BD (stopped)", True),
    ("x Brufen 400 PRN stopped", True),
    ("Ibugesic 400mg [discont.]", True),
    ("Claribid 500mg OD x 3 days (withdrawn)", True),
    ("T. Aldactone od - pt not taking since 2 months", True),
    ("VOVERAN 50 PRN - old, not taking now", True),
    ("STOP syr Potklor 15 ml 10ml HS", True),
    ("Tramazac 100 SR SOS for pain - omit", True),
    ("Tab Ecosprin 75 - discontinue", True),           # D-027: other forms of the training words
    ("T. Warf 5 OD - withheld", True),
    ("Dolo 650 SOS - not taken since 1 week", True),
    ("tab Aldactone 25 - ceased", True),
    ("T. Tremazac 50 SOS (old Rx)", False),           # an old prescription still being taken
    ("Ibugesic 400 mg if pain -- continue", False),
    ("Dolo 650 SOS", False),
])
def test_stopped_markers(raw: str, stopped: bool) -> None:
    assert is_stopped(raw) is stopped


def test_regimen_keeps_active_lines_and_says_why_others_are_out() -> None:
    meds = ("Tab Glycomet-GP 1", "Dolo 650 SOS (stopped)", "Physiotherapy", "Tab Zzqx")
    patient = Patient("P1", 70, "F", 60.0, 40.0, False, (), None,
                      tuple(MedicationEntry(m, i) for i, m in enumerate(meds)), 1)
    resolutions = (Resolution(meds[0], "", ("glimepiride", "metformin"), "exact", 1.0),
                   Resolution(meds[1], "", ("paracetamol",), "exact", 1.0),
                   Resolution(meds[2], "", (), "non_drug", 1.0),
                   Resolution(meds[3], "", (), "abstained", 0.2))
    regimen = build_regimen(patient, resolutions)
    assert [e.status for e in regimen.entries] == ["active", "stopped", "not_a_medicine", "unresolved"]
    assert regimen.generics == ("glimepiride", "metformin")      # a combination gives each generic
    assert [e.index for e in regimen.entries_for("metformin")] == [0]   # with its source entry


def test_mini_regimen(mini: Dataset) -> None:
    result = {p.patient.patient_id: p.rules.regimen for p in run_pipeline(mini).patients}
    assert result["H4P-MINI0003"].generics == ("warfarin",)                 # metformin stopped
    assert "ibuprofen" not in result["H4P-MINI0004"].generics               # "x ... stopped"
    assert result["H4P-MINI0002"].generics == ("ibuprofen", "pantoprazole")  # no "Physiotherapy"


STOPPED_LINE = re.compile(r"\b(stop|stopped|discontinued|discont|held|omit|withdrawn)\b|not taking",
                          re.IGNORECASE)


@requires_pack
def test_stopped_lines_resolve_but_never_reach_the_regimen(pack_train: Dataset) -> None:
    """Both directions of R1 on every stopped-looking training line: the resolution file names
    the drug, and no rule sees it."""
    with (data_dir() / "train_resolution.csv").open(newline="", encoding="utf-8") as handle:
        truth = {(r["patient_id"], r["written_token"]): r["resolved_generic"] for r in csv.DictReader(handle)}
    checked = 0
    for result in run_pipeline(pack_train).patients:
        for entry in result.rules.regimen.entries:
            if STOPPED_LINE.search(entry.raw):
                checked += 1
                assert ";".join(entry.generics) == truth[(result.patient.patient_id, entry.raw)]
                assert entry.status == "stopped", entry.raw
    assert checked >= 90
