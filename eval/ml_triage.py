"""Stage 3 challenger: gradient-boosted trees that score which alerts are worth a prescriber's time.

Part of ``python -m eval.ml_challenger``; off the scoring path like the rest of it.

The textbook version predicts adverse drug events or whether a prescriber acts on an alert. This
dataset records neither, so that model cannot be trained honestly here. What it does record is
which alerts match a real issue (train_labels.csv). So the model learns that instead, on the
alerts a standard hospital check raises (tools/ehr_reference.py), the noisiest source we have:

    target     1 if the alert matches a labelled issue that is not minor, else 0
    features   the patient (eGFR, age, number of lines, how many the formulary recognised,
               prescribers, pregnancy) and the alert (type, reference severity, how many alerts the
               patient has, the drug's renal tiers from renal_rules.csv)
    model      gradient-boosted regression trees on the logistic loss, standard library only
    threshold  alerts below it are held back; chosen on dev by the organisers' scorer, using
               out-of-fold scores from 5-fold cross-validation

Holdout is scored three ways with evaluate.py: the standard check as is, the standard check
with the model holding back its low-scoring alerts, and the shipped rules.
"""

from __future__ import annotations

import math
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval import official
from eval.pack import data_dir
from eval.truth import write_truth_subset
from medsafe.data.adapter import Dataset
from medsafe.data.schema import SEVERITIES
from tools.ehr_reference import EhrAlert, EhrResult, write_submission

FEATURES = ("severity_rank", "interaction", "duplicate", "renal", "egfr", "egfr_missing", "age", "lines",
            "recognised", "not_in_formulary", "prescribers", "pregnant", "patient_alerts",
            "renal_lowest_tier", "renal_highest_tier")
THRESHOLD_GRID = tuple(round(0.1 * i, 1) for i in range(1, 10))
FOLDS = 5


def alert_features(result: EhrResult, alert: EhrAlert, patient: Any, renal: Mapping[str, list[int]]) -> list[float]:
    """The numbers the trees split on for one alert. Missing eGFR is -1 with a flag, never 0."""
    tiers = renal.get(alert.drugs[0], []) if alert.issue_type == "renal_dose" else []
    recognised = sum(1 for e in result.entries if e.generic is not None)
    return [float(len(SEVERITIES) - 1 - SEVERITIES.index(alert.severity)),
            float(alert.issue_type == "interaction"), float(alert.issue_type == "duplicate_therapy"),
            float(alert.issue_type == "renal_dose"),
            float(patient.egfr) if patient.egfr is not None else -1.0, float(patient.egfr is None),
            float(patient.age or -1), float(len(result.entries)), float(recognised),
            float(len(result.entries) - recognised), float(patient.prescriber_count or -1),
            float(bool(patient.pregnant)), float(len(result.alerts)),
            float(min(tiers)) if tiers else -1.0, float(max(tiers)) if tiers else -1.0]


@dataclass
class Node:
    """A tree node: a split on ``feature`` at ``threshold``, or a leaf ``value``."""

    value: float = 0.0
    feature: int = -1
    threshold: float = 0.0
    left: Node | None = None
    right: Node | None = None

    def predict(self, x: Sequence[float]) -> float:
        """The leaf value this row falls into."""
        node = self
        while node.feature >= 0:
            node = node.left if x[node.feature] <= node.threshold else node.right
        return node.value


class BoostedTrees:
    """Gradient-boosted regression trees for a binary target, on the logistic loss.

    Newton leaf values, depth-limited trees, a minimum leaf size, L2 on leaf values. Splits are
    found by sorting each feature once per node and sweeping its gradient sums. Deterministic.
    """

    def __init__(self, trees: int = 60, depth: int = 3, rate: float = 0.15, min_leaf: int = 20, l2: float = 1.0):
        self.n_trees, self.depth, self.rate, self.min_leaf, self.l2 = trees, depth, rate, min_leaf, l2
        self.trees: list[Node] = []
        self.base = 0.0
        self.gain: dict[int, float] = defaultdict(float)

    def fit(self, X: Sequence[Sequence[float]], y: Sequence[int]) -> BoostedTrees:
        """Fit the trees. Returns self."""
        p = min(max(sum(y) / max(len(y), 1), 1e-6), 1 - 1e-6)
        self.base = math.log(p / (1 - p))
        score = [self.base] * len(X)
        for _ in range(self.n_trees):
            prob = [1 / (1 + math.exp(-s)) for s in score]
            grad = [yi - pi for yi, pi in zip(y, prob)]
            hess = [pi * (1 - pi) for pi in prob]
            tree = self._grow(X, grad, hess, list(range(len(X))), 0)
            self.trees.append(tree)
            score = [s + self.rate * tree.predict(x) for s, x in zip(score, X)]
        return self

    def _leaf(self, grad: Sequence[float], hess: Sequence[float], rows: Sequence[int]) -> float:
        return sum(grad[i] for i in rows) / (sum(hess[i] for i in rows) + self.l2)

    def _grow(self, X, grad, hess, rows: list[int], depth: int) -> Node:
        node = Node(value=self._leaf(grad, hess, rows))
        if depth >= self.depth or len(rows) < 2 * self.min_leaf:
            return node
        g_all, h_all = sum(grad[i] for i in rows), sum(hess[i] for i in rows)
        parent = g_all * g_all / (h_all + self.l2)
        best = (1e-9, -1, 0.0)
        for f in range(len(X[0])):
            ordered = sorted(rows, key=lambda i: X[i][f])
            g = h = 0.0
            for k, i in enumerate(ordered[:-1]):
                g += grad[i]; h += hess[i]  # noqa: E702
                if k + 1 < self.min_leaf or len(ordered) - k - 1 < self.min_leaf:
                    continue
                if X[i][f] == X[ordered[k + 1]][f]:
                    continue
                gain = g * g / (h + self.l2) + (g_all - g) ** 2 / (h_all - h + self.l2) - parent
                if gain > best[0]:
                    best = (gain, f, (X[i][f] + X[ordered[k + 1]][f]) / 2)
        gain, f, threshold = best
        if f < 0:
            return node
        self.gain[f] += gain
        node.feature, node.threshold = f, threshold
        node.left = self._grow(X, grad, hess, [i for i in rows if X[i][f] <= threshold], depth + 1)
        node.right = self._grow(X, grad, hess, [i for i in rows if X[i][f] > threshold], depth + 1)
        return node

    def prob(self, x: Sequence[float]) -> float:
        """The probability that this alert is worth showing."""
        s = self.base + self.rate * sum(t.predict(x) for t in self.trees)
        return 1 / (1 + math.exp(-s))


def auc(scored: Sequence[tuple[float, int]]) -> float:
    """Area under the ROC curve: the chance a worth-showing alert outscores a noise one."""
    pos = [s for s, y in scored if y]
    neg = [s for s, y in scored if not y]
    if not pos or not neg:
        return 0.0
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def dataset_rows(ehr: Mapping[str, EhrResult], patients: Mapping[str, Any], ids: Sequence[str],
                 truth: Mapping[tuple[str, str, frozenset], str], renal: Mapping[str, list[int]]):
    """(patient id, alert, features, label) for every standard-check alert on ``ids``."""
    out = []
    for pid in ids:
        result = ehr[pid]
        for alert in result.alerts:
            severity = truth.get((pid, alert.issue_type, frozenset(alert.drugs)))
            label = int(severity is not None and severity != "minor")
            out.append((pid, alert, alert_features(result, alert, patients[pid], renal), label))
    return out


def score_kept(ehr: Mapping[str, EhrResult], ids: frozenset[str], keep: Any, folder: Path) -> dict:
    """The organisers' score for the standard check on ``ids``, writing only alerts ``keep`` allows."""
    folder.mkdir(parents=True, exist_ok=True)
    predictions, resolution = folder / "H4_predictions.csv", folder / "H4_resolution.csv"
    write_submission([ehr[pid] for pid in sorted(ids)], predictions, resolution, keep)
    labels, truth_resolution = write_truth_subset(data_dir(), ids, folder / "truth")
    return official.score(predictions, resolution, labels, truth_resolution, folder / "score.json")


def run(dataset: Dataset, ehr: Mapping[str, EhrResult], dev: frozenset[str], holdout: frozenset[str],
        issues: Mapping[str, list[Any]]) -> dict[str, Any]:
    """Train on dev, pick the hold-back threshold with the scorer on dev, score holdout three ways."""
    patients = {p.patient_id: p for p in dataset.patients}
    truth = {(pid, i.issue_type, frozenset(i.drugs)): i.severity for pid, items in issues.items() for i in items}
    renal: dict[str, list[int]] = defaultdict(list)
    for rule in dataset.renal_rules:
        if rule.egfr_below is not None:
            renal[rule.generic].append(rule.egfr_below)
    dev_rows = dataset_rows(ehr, patients, sorted(dev), truth, renal)
    dev_ids = sorted(dev)
    fold_of = {pid: i % FOLDS for i, pid in enumerate(dev_ids)}
    out_of_fold: dict[int, float] = {}
    for fold in range(FOLDS):
        train_idx = [k for k, r in enumerate(dev_rows) if fold_of[r[0]] != fold]
        model = BoostedTrees().fit([dev_rows[k][2] for k in train_idx], [dev_rows[k][3] for k in train_idx])
        for k, r in enumerate(dev_rows):
            if fold_of[r[0]] == fold:
                out_of_fold[k] = model.prob(r[2])
    oof = {(r[0], id(r[1])): out_of_fold[k] for k, r in enumerate(dev_rows)}
    with tempfile.TemporaryDirectory() as tmp:
        grid = []
        for threshold in THRESHOLD_GRID:
            report = score_kept(ehr, dev, lambda pid, a, t=threshold: oof[(pid, id(a))] >= t, Path(tmp) / f"dev-{threshold}")
            grid.append((report["primary_score"], threshold))
        dev_score, threshold = max(grid, key=lambda g: (g[0], -g[1]))
        model = BoostedTrees().fit([r[2] for r in dev_rows], [r[3] for r in dev_rows])
        holdout_rows = dataset_rows(ehr, patients, sorted(holdout), truth, renal)
        scores = {(r[0], id(r[1])): model.prob(r[2]) for r in holdout_rows}
        as_is = score_kept(ehr, holdout, None, Path(tmp) / "as-is")
        triaged = score_kept(ehr, holdout, lambda pid, a: scores[(pid, id(a))] >= threshold, Path(tmp) / "triaged")
    importance = sorted(((FEATURES[f], round(g, 2)) for f, g in model.gain.items()), key=lambda kv: -kv[1])
    return {
        "training_alerts": len(dev_rows), "worth_showing": sum(r[3] for r in dev_rows),
        "threshold": threshold, "dev_score_at_threshold": dev_score, "folds": FOLDS,
        "holdout_alerts": len(holdout_rows),
        "holdout_auc": round(auc([(scores[(r[0], id(r[1]))], r[3]) for r in holdout_rows]), 4),
        "held_back": sum(1 for r in holdout_rows if scores[(r[0], id(r[1]))] < threshold),
        "held_back_worth_showing": sum(1 for r in holdout_rows if scores[(r[0], id(r[1]))] < threshold and r[3]),
        "importance": importance[:8],
        "official": {"standard check": as_is, "standard check + learned triage": triaged},
    }
