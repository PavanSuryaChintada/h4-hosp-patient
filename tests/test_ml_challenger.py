"""The ML challenger is a fair experiment: it predicts like a resolver, abstains under the same
contract, never sees the lines it is scored on, and gives the same answer every run."""

from __future__ import annotations

from medsafe.data.adapter import Dataset
from eval.ml_challenger import (NgramNearestNeighbour, Prediction, choose_thresholds, ngrams,
                                reference_examples, to_resolution)
from eval.records import TruthToken


def model(mini: Dataset) -> NgramNearestNeighbour:
    return NgramNearestNeighbour(reference_examples(mini) + [("Physiotherapy", ())])


def test_ngrams_are_padded_character_grams() -> None:
    grams = ngrams("pan")
    assert {"#pa", "pan", "an#", "#pan", "pan#"} <= set(grams)


def test_exact_and_misspelled_names_find_their_generic(mini: Dataset) -> None:
    m = model(mini)
    assert m.predict("Tab Glycomet 500 BD").label == ("metformin",)
    assert m.predict("Tab Glycomet 500 BD").similarity > 0.99
    assert m.predict("Tab Glycomett 500 BD").label == ("metformin",)
    assert m.predict("Tab Glycomet-GP 1 1-0-1").label == ("glimepiride", "metformin")
    assert m.predict("Physiotherapy").label == ()


def test_abstains_under_the_resolver_contract() -> None:
    weak = Prediction(("ibuprofen",), 0.2, 0.1, ((("ibuprofen",), 0.2),))
    close = Prediction(("ibuprofen",), 0.8, 0.79, ())
    assert to_resolution("x", weak, 0.3, 0.0).method == "abstained"
    assert to_resolution("x", close, 0.3, 0.05).abstain_reason == "ambiguous"
    sure = to_resolution("x", Prediction(("ibuprofen",), 0.9, 0.2, ()), 0.3, 0.05)
    assert sure.generics == ("ibuprofen",) and sure.method == "fuzzy"


def test_cross_validation_never_scores_a_line_with_a_model_that_saw_it(mini: Dataset) -> None:
    # Two patients with the same misspelling: with 5 folds over 2 patients, each is scored by a
    # model trained only on the other, so the score cannot come from memorising its own line.
    tokens = [TruthToken("P1", "Brufenn 400", frozenset({"ibuprofen"}), "misspelled_brand"),
              TruthToken("P2", "Brufenn 400", frozenset({"ibuprofen"}), "misspelled_brand")]
    chosen = choose_thresholds(mini, tokens)
    assert chosen["lines"] == 2 and chosen["cv_accuracy"] == 1.0


def test_same_line_same_answer(mini: Dataset) -> None:
    first, second = model(mini), model(mini)
    for raw in ("Brufen 400 tds", "T. PCM 650 SOS", "Tab Qxzrvy 400"):
        assert first.predict(raw) == second.predict(raw)
