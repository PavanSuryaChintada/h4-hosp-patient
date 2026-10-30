"""Every harness metric against numbers worked out by hand.

A wrong metric is worse than no metric: the pipeline gets tuned towards it with total
confidence. Each expected value below is computed in the comment beside it.
"""

from __future__ import annotations

import pytest

from eval.metrics import (count_by_severity, covers, index_resolutions, recall, recall_by,
                          resolution_metrics)
from eval.records import Alert, Issue, Resolution, TruthToken


def issue(pid: str, kind: str, drugs: tuple[str, ...], severity: str, near: bool = False) -> Issue:
    """Shorthand for a true issue."""
    return Issue(pid, kind, frozenset(drugs), severity, near)


def alert(pid: str, kind: str, drugs: tuple[str, ...], severity: str) -> Alert:
    """Shorthand for a raised alert."""
    return Alert(pid, kind, frozenset(drugs), severity)


A = issue("P1", "interaction", ("warfarin", "ibuprofen"), "major")
B = issue("P1", "renal_dose", ("metformin",), "major", near=True)
C = issue("P2", "duplicate_therapy", ("paracetamol",), "contraindicated")
D = issue("P2", "interaction", ("calcium carbonate", "levothyroxine"), "minor")
ALERTS = [alert("P1", "interaction", ("ibuprofen", "warfarin"), "moderate"),      # A, wrong severity
          alert("P2", "duplicate_therapy", ("paracetamol",), "contraindicated"),  # C
          alert("P2", "interaction", ("aspirin", "clopidogrel"), "major")]        # matches nothing


def test_covers_is_the_scorers_exact_key() -> None:
    assert covers(ALERTS[0], A)                       # severity does not affect the match
    assert not covers(alert("P2", "interaction", ("warfarin", "ibuprofen"), "major"), A)
    assert not covers(alert("P1", "duplicate_therapy", ("warfarin", "ibuprofen"), "major"), A)
    assert not covers(alert("P1", "interaction", ("warfarin", "ibuprofen", "aspirin"), "major"), A)


def test_recall_and_recall_by() -> None:
    serious = [i for i in (A, B, C, D) if i.serious]   # A, B, C
    assert recall(serious, ALERTS) == pytest.approx(2 / 3)
    assert recall([], ALERTS) is None
    assert recall_by([A, B, C, D], ALERTS, lambda i: i.severity) == {
        "contraindicated": 1.0, "major": 0.5, "minor": 0.0}          # C; A of A,B; not D
    assert not D.serious and C.serious


def test_count_by_severity_keeps_the_published_order() -> None:
    counts = count_by_severity(ALERTS + [alert("P3", "renal_dose", ("x",), "severe")])
    assert list(counts) == ["contraindicated", "major", "moderate", "minor", "severe"]
    assert counts == {"contraindicated": 1, "major": 1, "moderate": 1, "minor": 0, "severe": 1}


def test_resolution_metrics() -> None:
    def truth(pid: str, token: str, generics: tuple[str, ...], kind: str) -> TruthToken:
        return TruthToken(pid, token, frozenset(generics), kind)

    def ours(pid: str, token: str, generics: tuple[str, ...], method: str) -> Resolution:
        return Resolution(pid, token, frozenset(generics), method)

    tokens = [
        truth("P1", "Warf 5", ("warfarin",), "exact_brand"),                         # right
        truth("P1", "Glycomet-GP 1", ("glimepiride", "metformin"), "exact_brand"),   # right
        truth("P1", "Glycomet-GP 2", ("glimepiride", "metformin"), "exact_brand"),   # FALSE: half
        truth("P1", "Lasx 40", ("furosemide",), "misspelled_brand"),                 # FALSE
        truth("P1", "Colcy", ("colchicine",), "misspelled_brand"),                   # abstained
        truth("P1", "Physiotherapy", (), "non_drug"),                                # right
        truth("P2", "BP charting", (), "non_drug"),                                  # FALSE
        truth("P2", "Dolo 650", ("paracetamol",), "exact_brand"),                    # right
    ]
    predicted = index_resolutions([
        ours("P1", "Warf 5", ("warfarin",), "exact"),
        ours("P1", "Glycomet-GP 1", ("glimepiride", "metformin"), "exact"),
        ours("P1", "Glycomet-GP 2", ("metformin",), "fuzzy"),
        ours("P1", "Lasx 40", ("losartan",), "fuzzy"),
        ours("P1", "Colcy", (), "abstained"),
        ours("P1", "Physiotherapy", (), "non_drug"),
        ours("P2", "BP charting", ("aspirin",), "fuzzy"),
        ours("P2", "  DOLO   650 ", ("paracetamol",), "exact"),    # matched as the scorer does
    ])
    m = resolution_metrics(tokens, predicted)
    assert m["lines"] == 8
    assert m["accuracy"] == pytest.approx(4 / 8)
    assert m["false_resolution_rate"] == pytest.approx(3 / 8)
    assert m["abstention_rate"] == pytest.approx(1 / 8)
    assert m["misspelled_accuracy"] == 0.0                         # Lasx, Colcy
    assert m["by_token_kind"]["exact_brand"] == {"lines": 4, "accuracy": 0.75, "false": 1,
                                                 "abstained": 0}
    assert m["by_token_kind"]["non_drug"] == {"lines": 2, "accuracy": 0.5, "false": 1,
                                              "abstained": 0}
    assert resolution_metrics(tokens, None) is None


def test_index_resolutions_keeps_the_first_of_duplicate_tokens() -> None:
    first = Resolution("P1", "Tab Telma 40", frozenset({"telmisartan"}), "exact")
    second = Resolution("P1", "tab  telma 40", frozenset(), "abstained")
    assert list(index_resolutions([first, second]).values()) == [first]
