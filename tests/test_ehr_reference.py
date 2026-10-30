"""The standard-check reproduction does what a typical CDS layer does, and nothing more.

It is the demo's comparison (docs/ui-demo.md), so these tests pin the behaviour a clinician
judge would check: exact names only, combinations unexpanded, every listed pair at the table
severity, and one flat renal warning that never reads eGFR.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from medsafe.data.adapter import Dataset
from medsafe.data.schema import MedicationEntry, Patient
from tools.ehr_reference import EhrTables, check_patient, match_line


@pytest.fixture(scope="module")
def tables(mini: Dataset) -> EhrTables:
    return EhrTables.from_dataset(mini)


def on_list(mini: Dataset, *lines: str, **context) -> Patient:
    """The first mini patient with ``lines`` as their medication list, and any context changed."""
    meds = tuple(MedicationEntry(raw, i) for i, raw in enumerate(lines))
    return replace(mini.patients[0], medications=meds, **context)


@pytest.mark.parametrize("raw, expected", [
    ("Tab Glycomet 500 BD", "metformin"),
    ("Dolo 650 SOS", "paracetamol"),
    ("tab paracetamol 650 if pain", "paracetamol"),
    ("Tab Glycomett 500 BD", None),          # one letter off: not in formulary
    ("T. PCM 650 SOS", None),                # abbreviation: not in formulary
    ("Tab Glycomet-GP 1 1-0-1", None),       # combination brand: never expanded
    ("T Telma-AM 0-0-1", None),
])
def test_only_exact_formulary_names_are_recognised(tables: EhrTables, raw: str, expected: str | None) -> None:
    assert match_line(raw, tables.formulary) == expected


def test_every_listed_pair_fires_at_table_severity_minor_included(mini: Dataset, tables: EhrTables) -> None:
    result = check_patient(on_list(mini, "Brufen 400 tds", "Tab Warf 2mg OD", "Crocin 500 sos"), tables)
    pairs = {(a.drugs, a.severity) for a in result.alerts if a.issue_type == "interaction"}
    assert pairs == {(("ibuprofen", "warfarin"), "major"), (("paracetamol", "warfarin"), "minor")}


def test_renal_warning_is_identical_at_any_egfr(mini: Dataset, tables: EhrTables) -> None:
    results = [check_patient(on_list(mini, "Brufen 400 tds", egfr=egfr), tables).alerts
               for egfr in (28.0, 80.0, None)]
    assert results[0] == results[1] == results[2]
    (renal,) = results[0]
    # The most restrictive tier (eGFR < 30: major), whatever the patient's value.
    assert (renal.issue_type, renal.drugs, renal.severity) == ("renal_dose", ("ibuprofen",), "major")


def test_check_reads_nothing_but_the_list(mini: Dataset, tables: EhrTables) -> None:
    base = on_list(mini, "Brufen 400 tds", "Tab Warf 2mg OD")
    other = replace(base, age=30, pregnant=True, diagnoses=("asthma",), allergies="NSAIDs", egfr=12.0)
    assert check_patient(base, tables).alerts == check_patient(other, tables).alerts


def test_duplicate_seen_only_when_both_lines_are_recognised(mini: Dataset, tables: EhrTables) -> None:
    seen = check_patient(on_list(mini, "Dolo 650 SOS", "Crocin 500 sos"), tables)
    assert [(a.issue_type, a.drugs, a.severity, a.entries) for a in seen.alerts] == [
        ("duplicate_therapy", ("paracetamol",), "major", (0, 1))]
    # "PCM" is not a formulary name, so the same duplicate is invisible.
    missed = check_patient(on_list(mini, "Dolo 650 SOS", "T. PCM 650 SOS"), tables)
    assert missed.alerts == ()
    assert [e.generic for e in missed.entries] == ["paracetamol", None]


def test_metformin_inside_a_combination_is_never_checked(mini: Dataset, tables: EhrTables) -> None:
    result = check_patient(on_list(mini, "Tab Glycomet-GP 1 1-0-1", "tab Glycomet 500 BD", egfr=28.0), tables)
    assert [e.generic for e in result.entries] == [None, "metformin"]
    assert not any(a.issue_type == "duplicate_therapy" for a in result.alerts)


def test_same_list_same_alerts(mini: Dataset, tables: EhrTables) -> None:
    for patient in mini.patients:
        assert check_patient(patient, tables) == check_patient(patient, tables)
