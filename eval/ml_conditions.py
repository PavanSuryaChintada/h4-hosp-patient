"""Stage 2 challenger: a learned reader for conditions and negation in diagnosis and allergy text.

Part of ``python -m eval.ml_challenger``; off the scoring path like the rest of it.

The contraindication check needs to know which conditions a patient has, from free text full of
abbreviations, typos and negations ("BA", "sugar", "no h/o asthma", "PUD ruled out"). The shipped
reader is rules (medsafe.rules.conditions). This one is learned:

    examples   (patient, condition) pairs from the dev split, labelled from train_labels.csv
               without ever being told the condition: a condition is ABSENT when a drug on the list
               that it contraindicates carries no contraindication label; PRESENT when a drug that
               only this condition explains carries one. Ambiguous pairs are left out.
    features   every word of the text, tagged with the condition and with whether it sits in a
               negated span ("no", "denies", "ruled out"...); plus how closely a clause spells the
               condition's name or example terms (character trigrams), in or out of a negated span
    model      logistic regression, trained by stochastic gradient descent, standard library only;
               the decision threshold chosen by 5-fold cross-validation inside dev

It is scored by swapping it for the shipped reader inside the unchanged rule engine, so the only
difference between the two holdout submissions is who read the diagnosis text.
"""

from __future__ import annotations

import math
import random
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from unittest import mock

from medsafe.data.adapter import Dataset
from medsafe.rules.conditions import ConditionMatch

TEXT_KINDS = ("diagnosis", "allergy")
PRE_NEGATION = frozenset({"no", "not", "denies", "denied", "nil", "without", "never", "absent", "free"})
POST_NEGATION = frozenset({"ruled", "excluded", "unlikely", "negative"})
THRESHOLD_GRID = tuple(round(0.2 + 0.05 * i, 2) for i in range(13))     # 0.20 .. 0.80
FOLDS = 5
SEED = 2026


def tokens(clause: str) -> tuple[list[str], list[bool]]:
    """A clause's words, lowercased, and whether each sits in a negated span.

    A word after a leading negation word ("no h/o asthma") is negated; every word of a clause
    with a trailing one ("asthma ruled out") is. The model learns what each tagged word means.
    """
    words = re.findall(r"[a-z0-9]+", clause.lower())
    negated, after = [], False
    for word in words:
        after = after or word in PRE_NEGATION
        negated.append(after)
    if any(w in POST_NEGATION for w in words):
        negated = [True] * len(words)
    return words, negated


def trigrams(text: str) -> set[str]:
    """Character trigrams of a lowercased, space-padded string."""
    padded = f" {text.lower()} "
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


@dataclass(frozen=True)
class Condition:
    """One text condition the contraindication table uses, and the ways its name is written."""

    condition_id: str
    kind: str
    terms: tuple[frozenset[str], ...]          # trigram sets of the name and example terms


def text_conditions(dataset: Dataset) -> dict[str, Condition]:
    """The diagnosis and allergy conditions in the reference tables, with their written terms."""
    out = {}
    for cid, c in dataset.conditions.items():
        if c.kind in TEXT_KINDS:
            names = [cid.replace("_", " "), c.name or "", *c.example_terms]
            out[cid] = Condition(cid, c.kind, tuple(trigrams(n) for n in names if n.strip()))
    return out


def clauses_of(diagnoses: Sequence[str], allergies: str | None, kind: str) -> list[str]:
    """The text a condition of ``kind`` is read from: diagnoses for a diagnosis, allergies for an allergy."""
    text = list(diagnoses) if kind == "diagnosis" else [allergies or ""]
    return [c for t in text for c in re.split(r"[;,()\n]", t) if c.strip()]


def features(clauses: Iterable[str], condition: Condition) -> list[str]:
    """The sparse binary features of one (patient text, condition) pair."""
    cid = condition.condition_id
    out = {"bias", f"c={cid}"}
    for clause in clauses:
        words, negated = tokens(clause)
        for word, neg in zip(words, negated):
            out.add(f"{cid}|{'~' if neg else ''}{word}")
        grams = trigrams(" ".join(words))
        best = max((len(grams & t) / math.sqrt(len(grams) * len(t)) for t in condition.terms if grams and t), default=0.0)
        out.add(f"{'neg' if any(negated) else 'pos'}sim{min(int(best * 5), 4)}")
    return sorted(out)


class Logistic:
    """Binary logistic regression on sparse binary features, by stochastic gradient descent.

    Deterministic: a fixed seed orders the examples in every epoch.
    """

    def __init__(self, epochs: int = 25, rate: float = 0.2, l2: float = 1e-4):
        self.epochs, self.rate, self.l2 = epochs, rate, l2
        self.weights: dict[str, float] = defaultdict(float)

    def fit(self, rows: Sequence[list[str]], labels: Sequence[int]) -> Logistic:
        """Learn the weights. Returns self."""
        order = list(range(len(rows)))
        rng = random.Random(SEED)
        for epoch in range(self.epochs):
            rng.shuffle(order)
            rate = self.rate / (1 + epoch * 0.2)
            for i in order:
                error = labels[i] - self.prob(rows[i])
                for f in rows[i]:
                    self.weights[f] += rate * (error - self.l2 * self.weights[f])
        return self

    def prob(self, row: Iterable[str]) -> float:
        """The probability that the condition is present."""
        z = sum(self.weights.get(f, 0.0) for f in row)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


@dataclass(frozen=True)
class Example:
    """One labelled (patient, condition) pair."""

    patient_id: str
    condition_id: str
    present: int


def weak_labels(results: Sequence[Any], issues: Mapping[str, list[Any]], dataset: Dataset,
                conditions: Mapping[str, Condition]) -> list[Example]:
    """Label (patient, condition) pairs from the contraindication labels, without condition labels.

    Only conditions that could change an alert are candidates: those contraindicating a drug on
    the patient's current regimen. Absent: none of those drugs carries a contraindication label.
    Present: a drug carries one and this condition is its only possible explanation (no other
    text condition on it, and no pregnancy rule that applies). Everything else is skipped.
    """
    rows_for: dict[str, set[str]] = defaultdict(set)              # condition -> drugs
    explains: dict[str, set[str]] = defaultdict(set)              # drug -> text conditions
    pregnancy_drugs = {c.generic for c in dataset.contraindications if c.condition_id == "pregnancy"}
    for c in dataset.contraindications:
        if c.condition_id in conditions:
            rows_for[c.condition_id].add(c.generic)
            explains[c.generic].add(c.condition_id)
    out = []
    for result in results:
        patient = result.patient
        regimen = set(result.rules.regimen.generics)
        flagged = {next(iter(i.drugs)) for i in issues.get(patient.patient_id, []) if i.issue_type == "contraindication"}
        for cid, drugs in sorted(rows_for.items()):
            candidates = drugs & regimen
            if not candidates:
                continue
            if not candidates & flagged:
                out.append(Example(patient.patient_id, cid, 0))
                continue
            for drug in sorted(candidates & flagged):
                pregnancy = patient.pregnant and (drug in pregnancy_drugs or (
                    dataset.drugs[drug].pregnancy_category in ("D", "X") if drug in dataset.drugs else False))
                if explains[drug] == {cid} and not pregnancy:
                    out.append(Example(patient.patient_id, cid, 1))
                    break
    return out


class LearnedReader:
    """The trained model behind the interface the rule engine calls: detect_conditions(diagnoses, allergies)."""

    def __init__(self, model: Logistic, conditions: Mapping[str, Condition], threshold: float):
        self.model, self.conditions, self.threshold = model, conditions, threshold

    def __call__(self, diagnoses: Sequence[str], allergies: str | None) -> ConditionMatch:
        """Every text condition whose probability reaches the threshold is present."""
        present, evidence = set(), {}
        for cid, condition in self.conditions.items():
            p = self.model.prob(features(clauses_of(diagnoses, allergies, condition.kind), condition))
            if p >= self.threshold:
                present.add(cid)
                evidence[cid] = f"learned reader, p={p:.2f}"
        return ConditionMatch(frozenset(present), frozenset(), evidence)


def pair_features(results_by_id: Mapping[str, Any], conditions: Mapping[str, Condition], e: Example) -> list[str]:
    """Features of one labelled pair, from that patient's text."""
    patient = results_by_id[e.patient_id].patient
    condition = conditions[e.condition_id]
    return features(clauses_of(patient.diagnoses, patient.allergies, condition.kind), condition)


def f1(pairs: Sequence[tuple[int, int]]) -> float:
    """F1 of the 'present' class over (predicted, true) pairs."""
    tp = sum(1 for p, t in pairs if p and t)
    fp = sum(1 for p, t in pairs if p and not t)
    fn = sum(1 for p, t in pairs if not p and t)
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def train(dev_results: Sequence[Any], issues: Mapping[str, list[Any]], dataset: Dataset) -> tuple[LearnedReader, dict[str, Any]]:
    """Fit the reader on dev and choose its threshold by 5-fold cross-validation over dev patients."""
    conditions = text_conditions(dataset)
    by_id = {r.patient.patient_id: r for r in dev_results}
    examples = weak_labels(dev_results, issues, dataset, conditions)
    rows = [pair_features(by_id, conditions, e) for e in examples]
    labels = [e.present for e in examples]
    patients = sorted(by_id)
    fold_of = {pid: i % FOLDS for i, pid in enumerate(patients)}
    held: list[tuple[float, int]] = []
    for fold in range(FOLDS):
        train_idx = [i for i, e in enumerate(examples) if fold_of[e.patient_id] != fold]
        model = Logistic().fit([rows[i] for i in train_idx], [labels[i] for i in train_idx])
        held += [(model.prob(rows[i]), labels[i]) for i, e in enumerate(examples) if fold_of[e.patient_id] == fold]
    grid = [(f1([(int(p >= t), y) for p, y in held]), t) for t in THRESHOLD_GRID]
    best_f1, threshold = max(grid, key=lambda g: (round(g[0], 6), -g[1]))
    model = Logistic().fit(rows, labels)
    return LearnedReader(model, conditions, threshold), {
        "examples": len(examples), "present": sum(labels), "threshold": threshold,
        "cv_f1": round(best_f1, 4), "folds": FOLDS}


def pair_accuracy(results: Sequence[Any], examples: Sequence[Example], reader: Any) -> dict[str, Any]:
    """How a reader does on labelled (patient, condition) pairs: precision and recall of 'present'."""
    by_id = {r.patient.patient_id: r for r in results}
    pairs = []
    for e in examples:
        patient = by_id[e.patient_id].patient
        found = reader(patient.diagnoses, patient.allergies).present
        pairs.append((int(e.condition_id in found), e.present))
    tp = sum(1 for p, t in pairs if p and t)
    return {"pairs": len(pairs), "present": sum(t for _, t in pairs),
            "precision": round(tp / max(sum(p for p, _ in pairs), 1), 4),
            "recall": round(tp / max(sum(t for _, t in pairs), 1), 4), "f1": round(f1(pairs), 4)}


def patched(reader: Any):
    """A context in which the shipped rule engine reads conditions with ``reader``."""
    return mock.patch("medsafe.rules.engine.detect_conditions", reader)
