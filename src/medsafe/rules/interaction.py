"""Interaction: every pair of different generics in the regimen that interactions.csv lists.

Components of one combination product count too: they are two generics taken together.
Severity and action are the table's.
"""

from __future__ import annotations

from itertools import combinations

from medsafe.rules.regimen import Regimen
from medsafe.rules.tables import RuleTables
from medsafe.rules.types import Finding


def check_interactions(regimen: Regimen, tables: RuleTables) -> list[Finding]:
    """One finding per listed pair of generics in the regimen, pairs in alphabetical order."""
    findings = []
    for a, b in combinations(regimen.generics, 2):
        pair = tables.interactions.get(frozenset((a, b)))
        if pair is not None:
            findings.append(Finding(
                issue_type="interaction", drugs=(a, b), severity=pair.severity,
                action=pair.action or f"Review {a} with {b}", rule_id=f"INTERACTION:{a}+{b}",
                evidence={"table": "interactions.csv", "mechanism": pair.mechanism},
                raw_drugs=regimen.raw_for((a, b)), confidence=regimen.confidence_for((a, b))))
    return findings
