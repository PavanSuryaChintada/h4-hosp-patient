"""R3-R6: the four rule families, exactly as the pack's label engine defines them."""

from __future__ import annotations

import csv
from dataclasses import replace

import pytest

from conftest import MINI_DIR, requires_pack
from eval.metrics import rule_fidelity
from eval.pack import data_dir
from eval.trace import traces_from
from eval.truth import load_truth
from medsafe.data.adapter import Dataset
from medsafe.data.schema import DuplicateGroup, MedicationEntry, Patient
from medsafe.pipeline import run_pipeline
from medsafe.resolve.resolver import Resolution
from medsafe.rules.contraindication import check_contraindications
from medsafe.rules.duplicate import check_duplicates
from medsafe.rules.regimen import build_regimen
from medsafe.rules.renal import check_renal
from medsafe.rules.tables import RuleTables


@pytest.fixture(scope="module")
def tables(mini: Dataset) -> RuleTables:
    """The mini fixtures' tables, indexed."""
    return RuleTables.build(mini)


def regimen(*lines: tuple[str, tuple[str, ...]]):
    """A regimen of active lines, each (raw, generics)."""
    patient = Patient("P1", 60, "F", 60.0, 50.0, False, (), None,
                      tuple(MedicationEntry(raw, i) for i, (raw, _) in enumerate(lines)), 1)
    return build_regimen(patient, [Resolution(raw, "", g, "exact", 1.0) for raw, g in lines])


def keys(findings) -> set[tuple[str, tuple[str, ...], str]]:
    """(issue type, drugs, severity) of each finding."""
    return {(f.issue_type, f.drugs, f.severity) for f in findings}


def test_mini_findings_equal_the_hand_worked_labels(mini: Dataset) -> None:
    with (MINI_DIR / "train_labels.csv").open(newline="", encoding="utf-8") as handle:
        true = {(r["patient_id"], r["issue_type"], tuple(sorted(r["drugs_involved"].split(";"))),
                 r["severity"]) for r in csv.DictReader(handle)}
    ours = {(p.patient.patient_id, f.issue_type, f.drugs, f.severity)
            for p in run_pipeline(mini).patients for f in p.findings}
    assert ours == true


def test_paracetamol_from_two_products_is_major(tables: RuleTables) -> None:
    found = keys(check_duplicates(regimen(("Dolo 650", ("paracetamol",)),
                                          ("Combiflam", ("ibuprofen", "paracetamol"))), tables))
    assert ("duplicate_therapy", ("paracetamol",), "major") in found


def test_components_of_one_combination_never_duplicate_each_other(tables: RuleTables) -> None:
    same_group = replace(tables, drug_group={**tables.drug_group, "amlodipine": "ccb", "telmisartan": "ccb"},
                         groups={**tables.groups, "ccb": DuplicateGroup("ccb", "test", "major", "Keep one", ())})
    assert check_duplicates(regimen(("Telma-AM", ("amlodipine", "telmisartan"))), same_group) == []
    found = keys(check_duplicates(regimen(("Telma-AM", ("amlodipine", "telmisartan")),
                                          ("Amlong 5", ("amlodipine",))), same_group))
    assert found == {("duplicate_therapy", ("amlodipine",), "major"),       # same drug, two entries
                     ("duplicate_therapy", ("amlodipine", "telmisartan"), "major")}  # different entries


def test_a_drug_with_no_group_duplicates_at_moderate(tables: RuleTables) -> None:
    found = keys(check_duplicates(regimen(("Warf 5", ("warfarin",)), ("warfarin 2", ("warfarin",))), tables))
    assert found == {("duplicate_therapy", ("warfarin",), "moderate")}


@pytest.mark.parametrize(("egfr", "expected"), [
    (None, set()), (45.0, set()), (44.9, {"moderate"}), (30.0, {"moderate"}), (29.0, {"major"}),
])
def test_renal_is_strict_and_takes_the_most_restrictive_tier(tables: RuleTables, egfr, expected) -> None:
    findings = check_renal(regimen(("Glycomet 500", ("metformin",))), egfr, tables)
    assert {f.severity for f in findings} == expected


def test_contraindication_one_per_drug_at_the_most_severe_level(tables: RuleTables) -> None:
    warfarin = regimen(("Warf 2", ("warfarin",)))
    assert keys(check_contraindications(warfarin, frozenset(), True, tables)) == {
        ("contraindication", ("warfarin",), "contraindicated")}             # table row + letter X
    assert check_contraindications(warfarin, frozenset(), False, tables) == []
    assert check_contraindications(warfarin, frozenset(), None, tables) == []
    atenolol = regimen(("Tenormin 50", ("atenolol",)))
    assert keys(check_contraindications(atenolol, frozenset({"asthma"}), True, tables)) == {
        ("contraindication", ("atenolol",), "major")}                       # letter D beats moderate


@requires_pack
def test_every_training_label_is_reproduced_exactly(pack_train: Dataset) -> None:
    """The label engine is deterministic and the tables authoritative: any gap is our bug."""
    traces = traces_from(run_pipeline(pack_train))
    report = rule_fidelity(load_truth(data_dir()).issues,
                           [f for t in traces.values() for f in t.findings])
    for issue_type, r in report.items():
        assert (r["missed"], r["false"], r["wrong_severity"]) == (0, 0, 0), (issue_type, r)
    assert report["interaction"]["true"] == 1834 and report["duplicate_therapy"]["true"] == 507
