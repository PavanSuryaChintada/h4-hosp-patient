"""The harness end to end: reports, baselines, the regression gate, miss diagnosis, the sweep."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from eval import run as eval_run
from eval import sweep as eval_sweep
from eval.records import Issue, PatientTrace, Resolution, TruthMedication, Alert
from eval.trace import diagnose, trace_patient
from eval.truth import load_truth
from medsafe.data.adapter import load_dataset
from medsafe.data.schema import MedicationEntry, Patient
from medsafe.pipeline import PatientResult

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="module")
def fixture_eval() -> eval_run.Evaluation:
    """The pipeline evaluated once on the fixtures."""
    return eval_run.evaluate(load_dataset(FIXTURES_DIR), load_truth(FIXTURES_DIR))


def edited_input(tmp_path: Path, patient_id: str, column: str, value: str) -> Path:
    """A copy of the fixtures (labels included) with one patient cell changed."""
    input_dir = tmp_path / "input"
    shutil.copytree(FIXTURES_DIR, input_dir)
    path = input_dir / "patients.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    for row in rows[1:]:
        if row[0] == patient_id:
            row[rows[0].index(column)] = value
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    return input_dir


# --- End to end -------------------------------------------------------------------------------

def test_run_writes_a_report_with_provenance_and_the_docs(tmp_path: Path,
                                                          capsys: pytest.CaptureFixture) -> None:
    docs = tmp_path / "evaluation.md"
    assert eval_run.main(["--reports-dir", str(tmp_path / "reports"), "--docs", str(docs)]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("Serious-issue recall        Alerts per patient")

    (report_path,) = (tmp_path / "reports").glob("*.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path.name.endswith(f"-{report['git_revision']}.json")
    for key in ("generated_at", "git_revision", "data_version", "stages_built", "settings",
                "metrics", "missed_near_misses", "baselines", "load"):
        assert key in report, key
    assert {"alert_cap", "min_confidence", "min_margin",
            "low_value_alert_penalty"} <= set(report["settings"])

    markdown = docs.read_text(encoding="utf-8")
    assert "Serious-issue recall" in markdown and "Alerts per patient" in markdown
    for miss in report["missed_near_misses"]:
        assert miss["patient_id"] in markdown and miss["missed_because"]


def test_missed_near_misses_are_listed_individually_with_reasons(
        fixture_eval: eval_run.Evaluation) -> None:
    m = fixture_eval.metrics
    assert m["near_misses"] == 30
    assert len(fixture_eval.missed_near_misses) == m["near_misses"] - m["near_misses_caught"]
    for miss in fixture_eval.missed_near_misses:
        assert miss["near_miss_because"] and miss["missed_because"] and miss["as_written"]


def test_evaluation_is_deterministic(fixture_eval: eval_run.Evaluation) -> None:
    again = eval_run.evaluate(load_dataset(FIXTURES_DIR), load_truth(FIXTURES_DIR))
    assert again.metrics == fixture_eval.metrics
    assert again.missed_near_misses == fixture_eval.missed_near_misses


def test_degraded_patient_is_still_evaluated_but_a_dropped_one_is_lost(tmp_path: Path) -> None:
    """D-001 in numbers: a bad weight keeps P0020's issues in play; no medications loses them."""
    degraded = edited_input(tmp_path / "a", "P0020", "weight_kg", "seventy")
    result = eval_run.evaluate(load_dataset(degraded), load_truth(degraded))
    reasons = {m["missed_because"] for m in result.missed_near_misses if m["patient_id"] == "P0020"}
    assert reasons and not any("not loaded" in r for r in reasons)

    dropped = edited_input(tmp_path / "b", "P0020", "medications", "")
    result = eval_run.evaluate(load_dataset(dropped), load_truth(dropped))
    reasons = {m["missed_because"] for m in result.missed_near_misses if m["patient_id"] == "P0020"}
    assert reasons == {"patient not loaded: dropped by the adapter (see the load report)"}


# --- Baselines: the mirror behaves as the brief describes ------------------------------------

def test_baselines_bracket_the_mirror(fixture_eval: eval_run.Evaluation) -> None:
    b = fixture_eval.baselines
    assert b["flag nothing"]["serious_recall"] == 0.0 and b["flag nothing"]["score"] == 0.0
    assert b["flag everything"]["serious_recall"] > 0.9
    assert b["flag everything"]["score"] == 0.0
    assert b["oracle"]["serious_recall"] == 1.0 and b["oracle"]["near_miss_recall"] == 1.0
    assert b["oracle"]["score"] > 0.9


# --- Regression gate --------------------------------------------------------------------------

@pytest.mark.parametrize(("before", "now", "ok"), [
    (0.60, 0.50, False), (0.50, 0.50, True), (0.50, 0.70, True), (None, 0.10, True),
    (0.50, None, False),
])
def test_compare_fails_only_when_serious_recall_drops(before: float | None, now: float | None,
                                                      ok: bool) -> None:
    passed, message = eval_run.compare({"metrics": {"serious_recall": now}},
                                       {"metrics": {"serious_recall": before}})
    assert passed is ok
    assert ("REGRESSION" in message) is (not ok)


def test_compare_flag_exits_non_zero_on_a_drop(tmp_path: Path) -> None:
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps({"git_revision": "abc1234",
                                    "metrics": {"serious_recall": 0.9}}), encoding="utf-8")
    argv = ["--reports-dir", str(tmp_path / "reports"), "--no-docs", "--compare", str(previous)]
    assert eval_run.main(argv) == 1


# --- Miss diagnosis, stage by stage -----------------------------------------------------------

ISSUE = Issue("P1", "interaction", frozenset({"warfarin", "ibuprofen"}), "high")
MEDS = [TruthMedication("P1", 0, "Warf 5", "warfarin", ("brand",)),
        TruthMedication("P1", 1, "Brufn", "ibuprofen", ("brand", "misspelled"))]
RIGHT = (Resolution("P1", 0, "warfarin", "exact"), Resolution("P1", 1, "ibuprofen", "fuzzy"))
FOUND = (Alert("P1", "interaction", frozenset({"warfarin", "ibuprofen"}), "low"),)


@pytest.mark.parametrize(("trace", "expected"), [
    (None, "patient not loaded"),
    (PatientTrace("P1", None, None, None), "name resolution not built yet"),
    (PatientTrace("P1", (RIGHT[0], Resolution("P1", 1, None, "abstained")), None, None),
     "'Brufn' abstained, so ibuprofen was never checked"),
    (PatientTrace("P1", (RIGHT[0], Resolution("P1", 1, "ibandronate", "fuzzy")), None, None),
     "'Brufn' resolved to ibandronate instead of ibuprofen"),
    (PatientTrace("P1", RIGHT, None, None), "rule engine not built yet"),
    (PatientTrace("P1", RIGHT, (), ()), "no interaction finding for ibuprofen + warfarin"),
    (PatientTrace("P1", RIGHT, FOUND, None), "alert budget and output not built yet"),
    (PatientTrace("P1", RIGHT, FOUND, ()), "found at low but not shipped"),
])
def test_diagnose_names_the_stage_that_lost_the_issue(trace: PatientTrace | None,
                                                      expected: str) -> None:
    assert expected in diagnose(ISSUE, trace, MEDS)


def test_trace_seam_refuses_a_stage_it_cannot_convert() -> None:
    patient = Patient("P1", 70, 60.0, 40.0, False, (), (MedicationEntry("Warf 5", 0),))
    with pytest.raises(NotImplementedError, match="Phase 2"):
        trace_patient(PatientResult(patient, (), resolutions=("not converted",)))


# --- Sweep ------------------------------------------------------------------------------------

def test_sweep_covers_the_grid_and_reports_flat_honestly(tmp_path: Path) -> None:
    rows = eval_sweep.sweep(load_dataset(FIXTURES_DIR), load_truth(FIXTURES_DIR))
    assert len(rows) == len(eval_sweep.ALERT_CAPS) * len(eval_sweep.MIN_CONFIDENCES) == 49
    assert eval_sweep.is_flat(rows)
    assert "**Flat" in eval_sweep.render_markdown(rows, FIXTURES_DIR)


def test_sweep_best_prefers_score_then_fewer_alerts_then_smaller_cap() -> None:
    def row(cap: int, conf: float, score: float, after: float) -> dict:
        return {"alert_cap": cap, "min_confidence": conf, "score": score, "alerts_after": after,
                "serious_recall": score}
    rows = [row(5, 0.7, 0.80, 3.0), row(4, 0.7, 0.80, 2.5), row(3, 0.7, 0.80, 2.5),
            row(8, 0.9, 0.79, 1.0)]
    assert (eval_sweep.best(rows)["alert_cap"], eval_sweep.best(rows)["alerts_after"]) == (3, 2.5)
    assert not eval_sweep.is_flat(rows)
