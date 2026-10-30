"""Contraindication: a regimen drug against the patient's conditions, allergies and pregnancy.

Each drug is checked against drug_disease_contraindications.csv for the conditions found in the
diagnosis text, the allergies found in the allergy text, and pregnancy (pregnant = Y only).
When pregnant, pregnancy letter X is contraindicated and D is major, in addition to the table.
A drug gets at most one finding, at the most severe applicable level.
"""

from __future__ import annotations

from collections.abc import Set

from medsafe.rules.regimen import Regimen
from medsafe.rules.tables import RuleTables
from medsafe.rules.types import SEVERITY_RANK, Finding

PREGNANCY = "pregnancy"
PREGNANCY_LETTER_SEVERITY = {"X": "contraindicated", "D": "major"}


def check_contraindications(regimen: Regimen, conditions: Set[str], pregnant: bool | None,
                            tables: RuleTables) -> list[Finding]:
    """At most one finding per regimen generic, at its most severe applicable level.

    Args:
        regimen: The current regimen.
        conditions: condition_ids present (from diagnoses and allergies), never negated ones.
        pregnant: True only when the pregnancy field says Y.
        tables: Indexed reference tables.
    """
    findings = []
    for generic in regimen.generics:
        candidates = []                                  # (rank, from_table, severity, action, why)
        for row in tables.contraindications.get(generic, ()):
            applies = pregnant is True if row.condition_id == PREGNANCY else row.condition_id in conditions
            if applies:
                candidates.append((SEVERITY_RANK[row.severity], 1, row.severity,
                                   row.action or f"Review {generic}: {row.condition_name}",
                                   row.condition_id))
        letter = tables.pregnancy_letter.get(generic)
        if pregnant is True and letter in PREGNANCY_LETTER_SEVERITY:
            severity = PREGNANCY_LETTER_SEVERITY[letter]
            candidates.append((SEVERITY_RANK[severity], 0, severity,
                               f"Pregnancy category {letter}: avoid {generic} in pregnancy; "
                               f"switch to a pregnancy-safe alternative", f"pregnancy_category_{letter}"))
        if candidates:
            _, _, severity, action, why = max(candidates, key=lambda c: (c[0], c[1], c[4]))
            findings.append(Finding(
                issue_type="contraindication", drugs=(generic,), severity=severity, action=action,
                rule_id=f"CONTRAINDICATION:{generic}:{why}",
                evidence={"because": why, "all_applicable": sorted(c[4] for c in candidates)},
                raw_drugs=regimen.raw_for((generic,)), confidence=regimen.confidence_for((generic,))))
    return findings
