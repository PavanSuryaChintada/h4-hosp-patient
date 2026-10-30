"""The harness: the split, the regression gate, miss diagnosis, and agreement with the official
scorer on the real pack."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import requires_scorer
from eval.records import Issue, PatientTrace, Resolution, TruthToken
from eval.run import compare, evaluate_split
from eval.split import HOLDOUT_SIZE, split_ids
from eval.trace import diagnose, trace_patient
from medsafe.data.adapter import Dataset
from medsafe.data.schema import MedicationEntry, Patient
from medsafe.pipeline import PatientResult

IDS = [f"P{n:04d}" for n in range(1, 1501)]


def test_split_is_fixed_disjoint_and_complete() -> None:
    dev, holdout, train = (split_ids(IDS, s) for s in ("dev", "holdout", "train"))
    assert (len(dev), len(holdout), len(train)) == (1200, HOLDOUT_SIZE, 1500)
    assert not dev & holdout and dev | holdout == train
    assert split_ids(reversed(IDS), "holdout") == holdout          # input order does not matter
    with pytest.raises(ValueError):
        split_ids(IDS, "validation")


def report(primary: float, serious: float) -> dict:
    """A minimal report for the regression gate."""
    return {"splits": {"holdout": {"official": {"primary_score": primary,
                                                "components": {"serious_recall": serious}}}}}


@pytest.mark.parametrize(("before", "now", "ok"), [
    ((0.50, 0.60), (0.50, 0.60), True), ((0.50, 0.60), (0.55, 0.70), True),
    ((0.50, 0.60), (0.49, 0.60), False), ((0.50, 0.60), (0.50, 0.59), False),
])
def test_compare_fails_when_the_holdout_score_or_recall_drops(before, now, ok) -> None:
    passed, message = compare(report(*now), report(*before))
    assert passed is ok and ("REGRESSION" in message) is (not ok)


ISSUE = Issue("P1", "interaction", frozenset({"warfarin", "ibuprofen"}), "major")
TOKENS = [TruthToken("P1", "Warf 5", frozenset({"warfarin"}), "exact_brand"),
          TruthToken("P1", "Brufn", frozenset({"ibuprofen"}), "misspelled_brand")]
RIGHT = (Resolution("P1", "Warf 5", frozenset({"warfarin"}), "exact"),
         Resolution("P1", "Brufn", frozenset({"ibuprofen"}), "fuzzy"))


@pytest.mark.parametrize(("trace", "expected"), [
    (None, "patient not loaded"),
    (PatientTrace("P1", None, None, None), "name resolution not built yet"),
    (PatientTrace("P1", (RIGHT[0], Resolution("P1", "Brufn", frozenset(), "abstained")), None, None),
     "'Brufn' was not resolved, so ibuprofen was never checked"),
    (PatientTrace("P1", (RIGHT[0], Resolution("P1", "Brufn", frozenset({"ibandronate"}), "fuzzy")),
                  None, None), "'Brufn' resolved to ibandronate instead of ibuprofen"),
    (PatientTrace("P1", RIGHT, None, None), "every drug resolved; rule engine not built yet"),
])
def test_diagnose_names_the_stage_that_lost_the_issue(trace, expected: str) -> None:
    assert expected in diagnose(ISSUE, trace, TOKENS)


def test_trace_seam_converts_findings_and_alerts() -> None:
    from medsafe.rules.types import Finding
    patient = Patient("P1", 70, "F", 60.0, 40.0, False, (), None, (MedicationEntry("Warf 5", 0),), 1)
    finding = Finding("interaction", ("aspirin", "warfarin"), "minor", "Review", "R")
    alert = {"issue_type": "renal_dose", "severity": "major", "drugs_involved": "metformin"}
    trace = trace_patient(PatientResult(patient, (), resolutions=(), findings=(finding,), alerts=(alert,)))
    assert trace.findings[0].drugs == frozenset({"aspirin", "warfarin"})
    assert trace.shipped[0].drugs == frozenset({"metformin"}) and trace.shipped[0].severity == "major"


@requires_scorer
def test_holdout_resolution_agrees_with_the_official_scorer(pack_train: Dataset, tmp_path: Path) -> None:
    """Our resolution accuracy is the scorer's, to the line; and every holdout near-miss has
    every drug resolved."""
    result = evaluate_split(pack_train, "holdout", work_dir=tmp_path, with_baselines=False)
    official = result["official"]["components"]["resolution_accuracy"]
    assert result["resolution"]["accuracy"] == pytest.approx(official, abs=1e-6)
    assert result["resolution"]["false_resolution_rate"] <= 0.02
    assert result["near_misses"] and all(n["drugs_resolved"] for n in result["near_misses"])
