"""Every harness metric against numbers worked out by hand.

A wrong metric is worse than no metric: the detector gets tuned towards it with total
confidence. Each expected value below is computed in the comment beside it.
"""

from __future__ import annotations

import pytest

from eval import mirror
from eval.metrics import (compute_metrics, count_by_severity, covers, false_positives_by_severity,
                          low_value_alerts, per_patient, recall, recall_by, resolution_metrics,
                          zero_alert_patients)
from eval.records import Alert, Issue, PatientTrace, Resolution, TruthMedication


def issue(pid: str, kind: str, drugs: tuple[str, ...], severity: str, near: bool = False) -> Issue:
    """Shorthand for a true issue."""
    return Issue(pid, kind, frozenset(drugs), severity, near_miss=near)


def alert(pid: str, kind: str, drugs: tuple[str, ...], severity: str,
          covers_: tuple[tuple[str, ...], ...] = ()) -> Alert:
    """Shorthand for a raised alert."""
    return Alert(pid, kind, frozenset(drugs), severity,
                 covers=frozenset(frozenset(c) for c in covers_))


# Three patients. Serious issues: A, B, C, E. Low: D. Near-misses: B, C.
A = issue("P1", "interaction", ("warfarin", "ibuprofen"), "high")
B = issue("P1", "renal", ("metformin",), "medium", near=True)
C = issue("P2", "duplicate", ("aspirin", "clopidogrel"), "medium", near=True)
D = issue("P2", "interaction", ("calcium", "iron"), "low")
E = issue("P3", "renal", ("digoxin",), "high")
ISSUES = [A, B, C, D, E]

SHIPPED_P1 = (alert("P1", "interaction", ("warfarin", "ibuprofen"), "high"),)           # catches A
SHIPPED_P2 = (alert("P2", "duplicate", ("aspirin", "clopidogrel"), "low"),              # catches C
              alert("P2", "interaction", ("ramipril", "spironolactone"), "medium"),     # false alarm
              alert("P2", "interaction", ("calcium", "iron"), "low"))                   # catches D
SHIPPED = list(SHIPPED_P1 + SHIPPED_P2)
FINDINGS_P1 = SHIPPED_P1 + (alert("P1", "interaction", ("warfarin", "aspirin"), "high"),
                            alert("P1", "renal", ("metformin",), "low"))
TRACES = {
    "P1": PatientTrace("P1", None, FINDINGS_P1, SHIPPED_P1),
    "P2": PatientTrace("P2", None, SHIPPED_P2, SHIPPED_P2),
    "P3": PatientTrace("P3", None, (), ()),
}


def test_covers_needs_same_patient_type_and_exact_drugs() -> None:
    assert covers(alert("P1", "interaction", ("ibuprofen", "warfarin"), "low"), A)
    assert not covers(alert("P2", "interaction", ("warfarin", "ibuprofen"), "high"), A)
    assert not covers(alert("P1", "duplicate", ("warfarin", "ibuprofen"), "high"), A)
    # Naming more drugs than the issue is not a match: no catching every pair at once.
    assert not covers(alert("P1", "interaction", ("warfarin", "ibuprofen", "aspirin"), "high"), A)


def test_collapsed_alert_covers_only_the_edges_it_lists() -> None:
    cluster = alert("P1", "interaction", ("warfarin", "ibuprofen", "aspirin"), "high",
                    covers_=(("warfarin", "ibuprofen"), ("warfarin", "aspirin")))
    assert covers(cluster, A)
    assert not covers(cluster, issue("P1", "interaction", ("ibuprofen", "aspirin"), "medium"))


def test_serious_recall_counts_a_low_alert_on_a_serious_issue() -> None:
    serious = [i for i in ISSUES if i.serious]
    assert recall(serious, SHIPPED) == pytest.approx(2 / 4)       # A and C of A, B, C, E
    assert recall([], SHIPPED) is None


def test_recall_by_issue_type_and_true_severity() -> None:
    serious = [i for i in ISSUES if i.serious]
    assert recall_by(serious, SHIPPED, lambda i: i.issue_type) == {
        "duplicate": 1.0, "interaction": 1.0, "renal": 0.0}       # C; A; neither B nor E
    assert recall_by(ISSUES, SHIPPED, lambda i: i.severity) == {
        "high": 0.5, "low": 1.0, "medium": 0.5}                   # A of A,E; D; C of B,C


def test_false_positives_and_low_value_alerts() -> None:
    assert false_positives_by_severity(SHIPPED, ISSUES) == {
        "high": 0, "medium": 1, "low": 0, "info": 0}              # only ramipril+spironolactone
    assert low_value_alerts(SHIPPED, ISSUES) == 2                 # the false alarm, and D (low)


def test_count_by_severity_keeps_order_and_unexpected_labels() -> None:
    counts = count_by_severity([alert("P1", "renal", ("x",), "medium"),
                                alert("P1", "renal", ("y",), "severe")])
    assert list(counts) == ["high", "medium", "low", "info", "severe"]
    assert counts["medium"] == 1 and counts["severe"] == 1


def test_per_patient_and_zero_alert_patients() -> None:
    assert per_patient(7, 2) == 3.5
    assert per_patient(5, 0) == 0.0
    assert zero_alert_patients(["P1", "P2", "P3"], SHIPPED, ISSUES) == {
        "count": 1, "with_serious_issue": 1}                      # P3, which has E


def test_compute_metrics_end_to_end() -> None:
    m = compute_metrics(ISSUES, TRACES, [])
    assert m["patients"] == 3
    assert (m["serious_issues"], m["serious_caught"]) == (4, 2)
    assert m["serious_recall"] == pytest.approx(0.5)
    assert (m["near_misses"], m["near_misses_caught"]) == (2, 1)  # C caught, B not
    assert m["alerts_per_patient_before"] == pytest.approx(6 / 3)  # 3 + 3 + 0 findings
    assert m["alerts_per_patient_after"] == pytest.approx(4 / 3)   # 1 + 3 + 0 shipped
    assert m["alerts_per_patient_by_severity"]["after"] == pytest.approx(
        {"high": 1 / 3, "medium": 1 / 3, "low": 2 / 3, "info": 0.0})
    assert m["low_value_alerts_per_patient"] == pytest.approx(2 / 3)
    assert m["resolution"] is None                                 # resolver not built


def test_mirror_score() -> None:
    m = compute_metrics(ISSUES, TRACES, [])
    assert mirror.score(m) == pytest.approx(0.5 - 0.05 * 2 / 3)   # 0.4667
    assert mirror.score({"serious_recall": None, "low_value_alerts_per_patient": 0.0}) == 0.0
    assert mirror.score({"serious_recall": 1.0, "low_value_alerts_per_patient": 0.0}) == 1.0
    assert mirror.score({"serious_recall": 0.9, "low_value_alerts_per_patient": 40.0}) == 0.0


def test_resolution_metrics() -> None:
    def line(i: int, raw: str, generic: str | None, *mangling: str) -> TruthMedication:
        return TruthMedication("P1", i, raw, generic, mangling)

    medications = [
        line(0, "Warf 5", "warfarin", "brand"),                     # exact, right
        line(1, "Brufen", "ibuprofen", "brand"),                    # exact, right
        line(2, "ibuprofn", "ibuprofen", "generic", "misspelled"),  # fuzzy, right
        line(3, "Lasx 40", "furosemide", "brand", "misspelled"),    # fuzzy, WRONG: false resolution
        line(4, "Becosules", None, "out_of_reference"),             # abstains, right
        line(5, "Colcy", "colchicine", "brand", "misspelled"),      # abstains, wrong but not false
    ]
    resolutions = [Resolution("P1", 0, "warfarin", "exact"), Resolution("P1", 1, "ibuprofen", "exact"),
                   Resolution("P1", 2, "ibuprofen", "fuzzy"), Resolution("P1", 3, "losartan", "fuzzy"),
                   Resolution("P1", 4, None, "abstained"), Resolution("P1", 5, None, "abstained")]
    r = resolution_metrics(medications, resolutions)
    assert r["lines"] == 6
    assert r["accuracy"] == pytest.approx(4 / 6)
    assert r["false_resolution_rate"] == pytest.approx(1 / 6)
    assert r["abstention_rate"] == pytest.approx(2 / 6)
    assert r["exact_match_rate"] == pytest.approx(2 / 6)
    assert r["fuzzy_accuracy"] == pytest.approx(1 / 2)
    assert r["misspelled_accuracy"] == pytest.approx(1 / 3)        # lines 2, 3, 5: only 2 right
    assert resolution_metrics(medications, None) is None
