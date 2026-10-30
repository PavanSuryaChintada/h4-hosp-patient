"""Which alerts go into the predictions file, and what each one says. One policy, in one place.

Minor issues are detected and shown in the clinician view, and left out of H4_predictions.csv.
The reason is clinical before it is a score: minor alerts drive alert fatigue, fatigue drives
dismissal, and dismissal buries the serious alert behind them. The scorer penalises minor
alerts because that is what happens in hospitals. Measured, the policy agrees: +0.0518 for a
perfect detector, +0.0050 for the pack baseline (docs/DECISIONS.md D-018).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from medsafe.data.schema import Patient
from medsafe.explain.limitations import alert_limitations
from medsafe.rules.engine import RuleResult

EMIT_MINOR = False


def submitted(alerts: Iterable[Mapping[str, Any]], emit_minor: bool = EMIT_MINOR) -> list[Mapping[str, Any]]:
    """The alerts that go into the predictions file: all of them, or all but the minor ones."""
    return [alert for alert in alerts if emit_minor or alert["severity"] != "minor"]


def alert_rows(patient: Patient, rules: RuleResult) -> list[dict[str, Any]]:
    """Every finding as a predictions-file row: the table's severity and action, unchanged,
    plus the confidence-and-limitations text the pack requires on every alert."""
    return [{"patient_id": patient.patient_id, "issue_type": f.issue_type, "severity": f.severity,
             "drugs_involved": ";".join(f.drugs), "suggested_action": f.action,
             "confidence": round(f.confidence, 4),
             "confidence_and_limitations": alert_limitations(f, patient, rules.regimen)}
            for f in rules.findings]
