"""Reference alert sets that bracket the mirror score.

They check the harness and ``eval.mirror``, not the detector. All three read the TRUE generics,
so they skip name resolution entirely:

    flag nothing      no alerts                                   the brief says: scores zero
    flag everything   every pair, every drug, every issue type   the brief says: near zero
    oracle            exactly the true issues, nothing else       the ceiling for this mirror
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import combinations
from typing import Any

from eval import mirror
from eval.metrics import compute_metrics
from eval.records import Alert, PatientTrace
from eval.truth import Truth


def flag_nothing(truth: Truth) -> list[Alert]:
    """No alerts at all."""
    return []


def flag_everything(truth: Truth) -> list[Alert]:
    """Every pair of drugs as an interaction and a duplicate; every drug as renal,
    contraindication and repeated-drug duplicate. All at high severity."""
    generics: dict[str, set[str]] = {}
    for medication in truth.medications:
        if medication.generic:
            generics.setdefault(medication.patient_id, set()).add(medication.generic)
    alerts = []
    for patient_id, drugs in sorted(generics.items()):
        for pair in combinations(sorted(drugs), 2):
            for issue_type in ("interaction", "duplicate"):
                alerts.append(Alert(patient_id, issue_type, frozenset(pair), "high"))
        for drug in sorted(drugs):
            for issue_type in ("renal", "contraindication", "duplicate"):
                alerts.append(Alert(patient_id, issue_type, frozenset((drug,)), "high"))
    return alerts


def oracle(truth: Truth) -> list[Alert]:
    """One alert per true issue, at its true severity."""
    return [Alert(i.patient_id, i.issue_type, i.drugs, i.severity, i.rule_id)
            for i in truth.issues]


BASELINES: dict[str, Callable[[Truth], list[Alert]]] = {
    "flag nothing": flag_nothing,
    "flag everything": flag_everything,
    "oracle": oracle,
}


def evaluate_baselines(truth: Truth, patient_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Score each baseline over the loaded patients. Returns the headline figures per baseline."""
    results = {}
    for name, make in BASELINES.items():
        by_patient: dict[str, list[Alert]] = {}
        for alert in make(truth):
            by_patient.setdefault(alert.patient_id, []).append(alert)
        traces = {p: PatientTrace(p, None, tuple(by_patient.get(p, ())),
                                  tuple(by_patient.get(p, ())))
                  for p in patient_ids}
        metrics = compute_metrics(truth.issues, traces, truth.medications)
        results[name] = {
            "serious_recall": metrics["serious_recall"],
            "near_miss_recall": metrics["near_miss_recall"],
            "alerts_per_patient": metrics["alerts_per_patient_after"],
            "low_value_alerts_per_patient": metrics["low_value_alerts_per_patient"],
            "score": mirror.score(metrics),
        }
    return results
