"""Every metric the harness reports. Pure functions over ``eval.records``; no IO.

A wrong metric is worse than no metric, because it gets tuned towards with total confidence.
Each function here has hand-computed cases in ``tests/test_metrics.py``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, TypeVar

from eval.records import SEVERITIES, Alert, Issue, PatientTrace, Resolution, TruthMedication

R = TypeVar("R", Alert, Issue)


def covers(alert: Alert, issue: Issue) -> bool:
    """True if ``alert`` answers for ``issue``. Our reading of how the scorer matches.

    Same patient, same issue type, and the alert names exactly the issue's drugs, or lists
    them among the edges it ``covers`` (a collapsed alert). Not a subset test: an alert naming
    every drug a patient takes must not count as catching every pair.
    """
    return (alert.patient_id == issue.patient_id and alert.issue_type == issue.issue_type
            and (alert.drugs == issue.drugs or issue.drugs in alert.covers))


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


def per_patient(count: float, n_patients: int) -> float:
    """``count`` divided by the number of patients; 0.0 for an empty cohort."""
    return count / n_patients if n_patients else 0.0


def count_by_severity(alerts: Iterable[Alert]) -> dict[str, int]:
    """Alert count per severity, in SEVERITIES order, then any unexpected labels sorted."""
    counts = Counter(alert.severity for alert in alerts)
    ordered = {severity: counts.pop(severity, 0) for severity in SEVERITIES}
    return {**ordered, **dict(sorted(counts.items()))}


def false_positives_by_severity(alerts: Sequence[Alert], issues: Sequence[Issue]) -> dict[str, int]:
    """Alerts that cover no true issue at all, counted by the alert's own severity."""
    index = _by_patient(issues)
    false = [a for a in alerts
             if not any(covers(a, issue) for issue in index.get(a.patient_id, ()))]
    return count_by_severity(false)


def low_value_alerts(alerts: Sequence[Alert], issues: Sequence[Issue]) -> int:
    """Alerts that cover no serious true issue: false alarms plus alerts on low-rated issues."""
    serious = _by_patient(i for i in issues if i.serious)
    return sum(1 for a in alerts
               if not any(covers(a, issue) for issue in serious.get(a.patient_id, ())))


def recall_by(issues: Sequence[Issue], alerts: Sequence[Alert],
              key: Callable[[Issue], str]) -> dict[str, float | None]:
    """Recall within each group of ``issues``, grouped by ``key``, groups sorted by name."""
    groups: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        groups[key(issue)].append(issue)
    return {name: recall(group, alerts) for name, group in sorted(groups.items())}


def resolution_metrics(medications: Sequence[TruthMedication],
                       resolutions: Sequence[Resolution] | None) -> dict[str, Any] | None:
    """Name-resolution accuracy against ground truth. None when resolution is not built.

    A line is correct when it resolves to its true generic, or abstains on a product that is
    not in the drug table. A false resolution names the wrong generic: the dangerous case,
    because it produces confidently wrong alerts.
    """
    if resolutions is None or not medications:
        return None
    by_line = {(r.patient_id, r.med_index): r for r in resolutions}
    total = len(medications)
    correct = abstained = false = 0
    fuzzy_total = fuzzy_correct = exact = 0
    misspelled_total = misspelled_correct = 0
    for medication in medications:
        resolution = by_line.get((medication.patient_id, medication.med_index))
        resolved = resolution.resolved if resolution else None
        method = resolution.method if resolution else "abstained"
        is_correct = resolved == medication.generic
        correct += is_correct
        abstained += resolved is None
        false += resolved is not None and not is_correct
        exact += method == "exact"
        if method == "fuzzy":
            fuzzy_total += 1
            fuzzy_correct += is_correct
        if "misspelled" in medication.mangling:
            misspelled_total += 1
            misspelled_correct += is_correct
    return {
        "lines": total,
        "accuracy": correct / total,
        "false_resolution_rate": false / total,
        "abstention_rate": abstained / total,
        "exact_match_rate": exact / total,
        "fuzzy_accuracy": fuzzy_correct / fuzzy_total if fuzzy_total else None,
        "misspelled_accuracy": misspelled_correct / misspelled_total if misspelled_total else None,
    }


def zero_alert_patients(patient_ids: Sequence[str], alerts: Iterable[Alert],
                        issues: Sequence[Issue]) -> dict[str, int]:
    """Patients with no shipped alert, and how many of them have a serious true issue."""
    alerted = {a.patient_id for a in alerts}
    with_serious = {i.patient_id for i in issues if i.serious}
    silent = [p for p in patient_ids if p not in alerted]
    return {"count": len(silent), "with_serious_issue": sum(p in with_serious for p in silent)}


def compute_metrics(issues: Sequence[Issue], traces: Mapping[str, PatientTrace],
                    medications: Sequence[TruthMedication]) -> dict[str, Any]:
    """Every metric for one run.

    Args:
        issues: All true issues, including those of patients the adapter dropped (they count
            as missed).
        traces: One trace per loaded patient, keyed by patient id.
        medications: What every medication line really is.

    Returns:
        A JSON-ready dict. Alerts-per-patient figures divide by the number of loaded patients.
    """
    n = len(traces)
    findings = [a for t in traces.values() for a in (t.findings or ())]
    shipped = [a for t in traces.values() for a in (t.shipped or ())]
    resolutions = (None if any(t.resolutions is None for t in traces.values())
                   else [r for t in traces.values() for r in t.resolutions or ()])
    serious = [i for i in issues if i.serious]
    near_misses = [i for i in issues if i.near_miss]
    low_value = low_value_alerts(shipped, issues)
    return {
        "patients": n,
        "serious_issues": len(serious),
        "serious_caught": sum(caught(serious, shipped)),
        "serious_recall": recall(serious, shipped),
        "near_misses": len(near_misses),
        "near_misses_caught": sum(caught(near_misses, shipped)),
        "near_miss_recall": recall(near_misses, shipped),
        "alerts_per_patient_before": per_patient(len(findings), n),
        "alerts_per_patient_after": per_patient(len(shipped), n),
        "alerts_per_patient_by_severity": {
            "before": {s: per_patient(c, n) for s, c in count_by_severity(findings).items()},
            "after": {s: per_patient(c, n) for s, c in count_by_severity(shipped).items()},
        },
        "low_value_alerts": low_value,
        "low_value_alerts_per_patient": per_patient(low_value, n),
        "false_positives_by_severity": false_positives_by_severity(shipped, issues),
        "serious_recall_by_issue_type": recall_by(serious, shipped, lambda i: i.issue_type),
        "recall_by_true_severity": recall_by(issues, shipped, lambda i: i.severity),
        "resolution": resolution_metrics(medications, resolutions),
        "zero_alert_patients": zero_alert_patients(list(traces), shipped, issues),
    }
