"""Renal dose: eGFR strictly below a tier's threshold, at the most restrictive tier.

Uses the recorded eGFR only. Missing eGFR means no renal finding: the labels have none either,
and the "CKD" diagnosis text is never read (pack README).
"""

from __future__ import annotations

from medsafe.rules.regimen import Regimen
from medsafe.rules.tables import RuleTables
from medsafe.rules.types import Finding


def check_renal(regimen: Regimen, egfr: float | None, tables: RuleTables) -> list[Finding]:
    """One finding per regimen generic whose eGFR falls under a tier; the lowest such tier wins."""
    if egfr is None:
        return []
    findings = []
    for generic in regimen.generics:
        applicable = [rule for rule in tables.renal.get(generic, ()) if egfr < rule.egfr_below]
        if applicable:
            tier = applicable[0]                       # tiers are sorted lowest threshold first
            findings.append(Finding(
                issue_type="renal_dose", drugs=(generic,), severity=tier.severity,
                action=tier.action or f"Review {generic} dose for eGFR {egfr:g}",
                rule_id=f"RENAL:{generic}<{tier.egfr_below}",
                evidence={"egfr": egfr, "egfr_below": tier.egfr_below},
                raw_drugs=regimen.raw_for((generic,)), confidence=regimen.confidence_for((generic,))))
    return findings
