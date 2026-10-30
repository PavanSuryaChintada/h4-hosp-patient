"""The stage 2 and 3 challengers learn what they claim to, label fairly, and repeat exactly.

Stage 2 reads conditions and negation from diagnosis text; stage 3 scores which alerts are worth
showing. Both are off the scoring path (eval/ml_challenger.py).
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from eval.ml_conditions import (ConditionMatch, Example, LearnedReader, Logistic, features, patched,
                                text_conditions, tokens, weak_labels)
from eval.ml_triage import BoostedTrees, auc
from eval.records import Issue
from medsafe.data.adapter import Dataset


def test_negation_spans() -> None:
    assert tokens("no h/o asthma") == (["no", "h", "o", "asthma"], [True, True, True, True])
    assert tokens("asthma ruled out")[1] == [True, True, True]
    assert tokens("bronchial asthma")[1] == [False, False]


def result(mini: Dataset, pid: str, generics: tuple[str, ...], diagnoses: tuple[str, ...] = ("asthma",)):
    """A stand-in pipeline result: a patient and their current regimen."""
    patient = replace(mini.patients[0], patient_id=pid, diagnoses=diagnoses, pregnant=False)
    return SimpleNamespace(patient=patient, rules=SimpleNamespace(regimen=SimpleNamespace(generics=generics)))


def test_weak_labels_never_guess(mini: Dataset) -> None:
    conditions = text_conditions(mini)
    results = [result(mini, "A", ("atenolol",)), result(mini, "B", ("atenolol",)), result(mini, "C", ("metformin",))]
    issues = {"A": [Issue("A", "contraindication", frozenset({"atenolol"}), "moderate")]}
    labels = weak_labels(results, issues, mini, conditions)
    # A: atenolol is flagged and only asthma explains it -> present. B: not flagged -> absent.
    # C: no drug asthma contraindicates -> not a candidate at all.
    assert labels == [Example("A", "asthma", 1), Example("B", "asthma", 0)]


def test_logistic_learns_negation_flips_meaning(mini: Dataset) -> None:
    asthma = text_conditions(mini)["asthma"]
    texts = [["asthma"], ["bronchial asthma"], ["BA"], ["no h/o asthma"], ["asthma ruled out"], ["HTN"]]
    labels = [1, 1, 1, 0, 0, 0]
    model = Logistic().fit([features(t, asthma) for t in texts] * 5, labels * 5)
    probs = [model.prob(features(t, asthma)) for t in texts]
    assert all(p > 0.5 for p in probs[:3]) and all(p < 0.5 for p in probs[3:])


def test_learned_reader_plugs_into_the_rule_engine(mini: Dataset) -> None:
    import medsafe.rules.engine as engine
    asthma = text_conditions(mini)["asthma"]
    model = Logistic().fit([features(["asthma"], asthma), features(["HTN"], asthma)] * 10, [1, 0] * 10)
    reader = LearnedReader(model, {"asthma": asthma}, 0.5)
    assert isinstance(reader(("bronchial asthma",), None), ConditionMatch)
    assert reader(("asthma",), None).present == {"asthma"}
    with patched(reader):
        assert engine.detect_conditions is reader
    assert engine.detect_conditions is not reader


def test_boosted_trees_learn_a_renal_threshold() -> None:
    # Worth showing only when it is a renal alert and eGFR is under 30: an interaction of two features.
    rows = [[float(egfr), float(renal)] for egfr in range(10, 120, 3) for renal in (0, 1)]
    labels = [int(r[1] == 1 and r[0] < 30) for r in rows]
    model = BoostedTrees(trees=40, depth=2, min_leaf=3).fit(rows, labels)
    assert auc([(model.prob(r), y) for r, y in zip(rows, labels)]) > 0.99
    again = BoostedTrees(trees=40, depth=2, min_leaf=3).fit(rows, labels)
    assert [model.prob(r) for r in rows] == [again.prob(r) for r in rows]


def test_auc_is_the_ranking_chance() -> None:
    assert auc([(0.9, 1), (0.1, 0)]) == 1.0
    assert auc([(0.1, 1), (0.9, 0)]) == 0.0
    assert auc([(0.5, 1), (0.5, 0)]) == 0.5
