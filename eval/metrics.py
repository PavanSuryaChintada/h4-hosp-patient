"""Metrics the official scorer does not report, and the ones we need to tune and diagnose.

Pure functions over ``eval.records``; no IO. The official score itself always comes from the
organisers' ``evaluate.py`` (``eval/official.py``). ``resolution_metrics`` must agree with its
resolution accuracy; ``tests/test_eval.py`` checks that on the real pack.

A wrong metric is worse than no metric. Each function has hand-computed cases in
``tests/test_metrics.py``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, TypeVar

from eval.records import SEVERITIES, Alert, Issue, Resolution, TruthToken
from medsafe.data.schema import ISSUE_TYPES
from medsafe.output.writer import token_key

R = TypeVar("R", Alert, Issue)


def covers(alert: Alert, issue: Issue) -> bool:
    """True if ``alert`` matches ``issue`` the way the official scorer matches: same patient,
    same issue type, exactly the same set of drugs."""
    return (alert.patient_id == issue.patient_id and alert.issue_type == issue.issue_type
            and alert.drugs == issue.drugs)


def _by_patient(records: Iterable[R]) -> dict[str, list[R]]:
    """Group alerts or issues by patient id."""
    grouped: dict[str, list[R]] = defaultdict(list)
    for record in records:
        grouped[record.patient_id].append(record)
    return grouped


def caught(issues: Sequence[Issue], alerts: Iterable[Alert]) -> list[bool]:
    """For each issue, whether any alert covers it. Same order as ``issues``."""
    index = _by_patient(alerts)
    return [any(covers(a, issue) for a in index.get(issue.patient_id, ())) for issue in issues]


def recall(issues: Sequence[Issue], alerts: Iterable[Alert]) -> float | None:
    """Share of ``issues`` covered by at least one alert. None when there are no issues."""
    if not issues:
        return None
    return sum(caught(issues, alerts)) / len(issues)


def recall_by(issues: Sequence[Issue], alerts: Sequence[Alert],
              key: Callable[[Issue], str]) -> dict[str, float | None]:
    """Recall within each group of ``issues``, grouped by ``key``, groups sorted by name."""
    groups: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        groups[key(issue)].append(issue)
    return {name: recall(group, alerts) for name, group in sorted(groups.items())}


def count_by_severity(alerts: Iterable[Alert]) -> dict[str, int]:
    """Alert count per severity, in SEVERITIES order, then any unexpected labels sorted."""
    counts = Counter(alert.severity for alert in alerts)
    ordered = {severity: counts.pop(severity, 0) for severity in SEVERITIES}
    return {**ordered, **dict(sorted(counts.items()))}


def resolution_metrics(tokens: Sequence[TruthToken],
                       resolutions: Mapping[tuple[str, str], Resolution] | None
                       ) -> dict[str, Any] | None:
    """Name-resolution quality against the true resolution of every written line.

    A line is correct when its set of generics is exactly the true set (an empty set is right
    for a non-medicine line), matched on (patient, token) the way the scorer matches. A false
    resolution names a set that is not the true one: the dangerous case, because it can raise a
    confidently wrong alert. An abstention names nothing for a real medicine.

    Args:
        tokens: True resolutions.
        resolutions: Our resolutions keyed by (patient_id, token_key(written_token)); None when
            resolution is not built.

    Returns:
        lines, accuracy, false_resolution_rate, abstention_rate, accuracy on misspelled lines,
        and accuracy, false resolutions and abstentions per token kind. None if not built.
    """
    if resolutions is None or not tokens:
        return None
    totals: Counter = Counter()
    by_kind: dict[str, Counter] = defaultdict(Counter)
    for token in tokens:
        ours = resolutions.get((token.patient_id, token_key(token.written_token)))
        generics = ours.generics if ours else frozenset()
        outcome = ("correct" if generics == token.generics
                   else "false" if generics else "abstained")
        totals[outcome] += 1
        by_kind[token.token_kind][outcome] += 1
        by_kind[token.token_kind]["lines"] += 1
        if token.token_kind.startswith("misspelled"):
            totals["misspelled"] += 1
            totals["misspelled_correct"] += outcome == "correct"
    lines = len(tokens)
    return {
        "lines": lines,
        "accuracy": totals["correct"] / lines,
        "false_resolution_rate": totals["false"] / lines,
        "abstention_rate": totals["abstained"] / lines,
        "false_resolutions": totals["false"],
        "abstentions": totals["abstained"],
        "misspelled_accuracy": (totals["misspelled_correct"] / totals["misspelled"]
                                if totals["misspelled"] else None),
        "by_token_kind": {kind: {"lines": c["lines"], "accuracy": c["correct"] / c["lines"],
                                 "false": c["false"], "abstained": c["abstained"]}
                          for kind, c in sorted(by_kind.items())},
    }


def rule_fidelity(issues: Sequence[Issue], findings: Iterable[Alert],
                  examples: int = 5) -> dict[str, dict[str, Any]]:
    """How exactly each rule family reproduces the labels, minor issues included.

    Per issue type: true count, our count, matched (same patient, type and drug set), missed,
    false, and matched-but-wrong-severity, with the first few missed and false cases as
    "patient: drug;drug" so each one can be reproduced.
    """
    true = {(i.patient_id, i.issue_type, i.drugs): i.severity for i in issues}
    ours = {(f.patient_id, f.issue_type, f.drugs): f.severity for f in findings}
    report = {}
    for issue_type in ISSUE_TYPES:
        t = {k: v for k, v in true.items() if k[1] == issue_type}
        o = {k: v for k, v in ours.items() if k[1] == issue_type}
        missed, false = sorted(set(t) - set(o)), sorted(set(o) - set(t))
        cite = lambda keys: [f"{k[0]}: {';'.join(sorted(k[2]))}" for k in keys[:examples]]
        report[issue_type] = {
            "true": len(t), "ours": len(o), "matched": len(set(t) & set(o)),
            "missed": len(missed), "false": len(false),
            "wrong_severity": sum(1 for k in set(t) & set(o) if t[k] != o[k]),
            "first_missed": cite(missed), "first_false": cite(false),
        }
    return report


def index_resolutions(resolutions: Iterable[Resolution]) -> dict[tuple[str, str], Resolution]:
    """Key resolutions by (patient_id, token_key) as the scorer does; first one wins."""
    indexed: dict[tuple[str, str], Resolution] = {}
    for resolution in resolutions:
        indexed.setdefault((resolution.patient_id, token_key(resolution.written_token)), resolution)
    return indexed
