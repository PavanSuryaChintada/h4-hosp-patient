"""The UI data file holds exactly what the pipeline produced, and says "not built" for the rest.

docs/phases/09-ui.md R1: the UI never recomputes. These tests hold the exporter to that: every
loaded patient and line is exported, unbuilt stages are null rather than empty, a built stage
with no converter fails loudly, and the file is the same on every run.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from conftest import MINI_DIR
from eval.truth import load_truth
from medsafe.data.adapter import Dataset
from medsafe.pipeline import run_pipeline
from tools.export_ui import SCHEMA_VERSION, build_export, medsafe_view

TOP_LEVEL = {"schema_version", "source", "stages", "settings", "patients", "workflow", "resolution",
             "cohort", "demo", "ehr_reference", "evaluation", "ml_challenger"}


@pytest.fixture(scope="module")
def export(mini: Dataset, tmp_path_factory: pytest.TempPathFactory) -> dict:
    truth = load_truth(MINI_DIR, {p.patient_id for p in mini.patients})
    return build_export(mini, run_pipeline(mini), truth, reports_dir=tmp_path_factory.mktemp("reports"),
                        score_ehr=False)


def test_shape_matches_the_ui_contract(export: dict) -> None:
    assert set(export) == TOP_LEVEL
    assert export["schema_version"] == SCHEMA_VERSION
    assert json.loads(json.dumps(export)) == export


def test_every_patient_and_every_line_is_exported_in_order(mini: Dataset, export: dict) -> None:
    assert [p["id"] for p in export["patients"]] == [p.patient_id for p in mini.patients]
    for patient, view in zip(mini.patients, export["patients"]):
        assert [m["raw"] for m in view["medications"]] == [m.raw for m in patient.medications]
        assert len(view["ehr"]["matched"]) == len(patient.medications)
        assert view["compare"]["medsafe"]["dropped"] == 0


def test_every_finding_is_exported_and_every_submitted_alert_has_one_action(mini: Dataset, export: dict) -> None:
    for result, view in zip(run_pipeline(mini).patients, export["patients"]):
        medsafe = view["medsafe"]
        assert len(medsafe["alerts"]) == len(result.findings)
        assert sum(a["submitted"] for a in medsafe["alerts"]) == len(result.alerts)
        assert all(a["submitted"] == (a["severity"] != "minor") for a in medsafe["alerts"])
        covered = [r for act in medsafe["actions"] for r in (act["covers"] if act["kind"] == "collapse" else [act["rank"]])]
        assert sorted(covered) == sorted(a["rank"] for a in medsafe["alerts"] if a["submitted"])
        assert "safe" not in medsafe["summary"].lower().split()
        assert view["compare"]["medsafe"]["actions"] == len(medsafe["actions"])


def test_renal_alert_carries_its_tier_and_the_header_shows_it(export: dict) -> None:
    first = export["patients"][0]                # eGFR 28, metformin inside Glycomet-GP
    renal = [a for a in first["medsafe"]["alerts"] if a["issue_type"] == "renal_dose"]
    assert renal and all(a["tier"]["egfr_below"] > 28 for a in renal)
    assert first["compare"]["medsafe"]["egfr_tier"]["severity"] == "major"


def test_an_unbuilt_stage_exports_as_null(mini: Dataset) -> None:
    result = run_pipeline(mini).patients[0]
    view = medsafe_view(replace(result, findings=None, rules=None))
    assert view["alerts"] is None and view["actions"] is None and view["collapse"] is None


def test_policy_comes_from_the_workflow_module(export: dict) -> None:
    from medsafe import workflow
    assert export["workflow"]["roles"] == list(workflow.ROLES)
    assert export["workflow"]["override_reasons"] == list(workflow.OVERRIDE_REASONS)
    assert export["workflow"]["entries"]["lab"] == ["egfr"]


def test_comparison_counts_combinations_the_standard_check_cannot_open(export: dict) -> None:
    first = export["patients"][0]                # Glycomet-GP 1 and Telma-AM on the list
    assert first["id"] == "H4P-MINI0001"
    brands = [m["raw"] for m in first["medications"] if m["combination"] == "brand"]
    assert brands == ["Tab Glycomet-GP 1 1-0-1", "T Telma-AM 0-0-1"]
    assert first["compare"]["medsafe"]["combinations_expanded"] == 2
    assert first["compare"]["ehr"]["combinations_unexpanded"] == 2
    assert first["compare"]["ehr"]["egfr_read"] is False


def test_label_column_is_present_for_training_patients_only(mini: Dataset, export: dict) -> None:
    assert any(m["truth"] for p in export["patients"] for m in p["medications"])
    test_export = build_export(mini, run_pipeline(mini), None, reports_dir=Path("missing"), score_ehr=False)
    assert all(m["truth"] is None for p in test_export["patients"] for m in p["medications"])
    assert test_export["demo"] is None


def test_same_input_same_file(mini: Dataset, export: dict, tmp_path: Path) -> None:
    truth = load_truth(MINI_DIR, {p.patient_id for p in mini.patients})
    again = build_export(mini, run_pipeline(mini), truth, reports_dir=tmp_path, score_ehr=False)
    assert json.dumps(again, sort_keys=True) == json.dumps(export, sort_keys=True)


def test_cohort_figures_add_up(export: dict) -> None:
    cohort = export["cohort"]
    assert sorted(cohort["queue_order"]) == sorted(p["id"] for p in export["patients"])
    assert sum(cohort["by_top_severity"].values()) == len(export["patients"])
    assert sum(s["patients"] for s in cohort["egfr_stages"]) == len(export["patients"])
    assert cohort["totals"]["medsafe_submitted"] == sum(
        a["submitted"] for p in export["patients"] for a in p["medsafe"]["alerts"])
    histogram = cohort["confidence_histogram"]
    counted = sum(map(sum, histogram["counts"].values())) + sum(histogram["below_first"].values())
    assert counted == sum(1 for p in export["patients"] for m in p["medications"] if m["method"] != "non_drug")


def test_queue_puts_the_most_severe_first(export: dict) -> None:
    rank = ("contraindicated", "major", "moderate", "minor", "none")
    by_id = {p["id"]: p for p in export["patients"]}
    order = [rank.index(by_id[i]["compare"]["medsafe"]["top_severity"]) for i in export["cohort"]["queue_order"]]
    assert order == sorted(order)
