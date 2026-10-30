"""Runs the four rule families for one patient. Does not filter, rank or cap: every finding,
minor ones included, comes back (the output policy decides what is submitted)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from medsafe.data.schema import ISSUE_TYPES, Patient
from medsafe.resolve.resolver import Resolution
from medsafe.rules.conditions import ConditionMatch, detect_conditions
from medsafe.rules.contraindication import check_contraindications
from medsafe.rules.duplicate import check_duplicates
from medsafe.rules.interaction import check_interactions
from medsafe.rules.regimen import Regimen, build_regimen
from medsafe.rules.renal import check_renal
from medsafe.rules.tables import RuleTables
from medsafe.rules.types import Finding


@dataclass(frozen=True)
class RuleResult:
    """One patient's regimen, the conditions found in their text, and every finding."""

    regimen: Regimen
    conditions: ConditionMatch
    findings: tuple[Finding, ...]


def run_rules(patient: Patient, resolutions: Sequence[Resolution], tables: RuleTables) -> RuleResult:
    """Build the regimen, read the conditions, and run all four checks.

    Returns:
        Findings ordered by issue type (interaction, duplicate, renal, contraindication), then
        by drugs. Deterministic.
    """
    regimen = build_regimen(patient, resolutions)
    conditions = detect_conditions(patient.diagnoses, patient.allergies)
    findings = (check_interactions(regimen, tables) + check_duplicates(regimen, tables)
                + check_renal(regimen, patient.egfr, tables)
                + check_contraindications(regimen, conditions.present, patient.pregnant, tables))
    order = {t: i for i, t in enumerate(ISSUE_TYPES)}
    return RuleResult(regimen, conditions,
                      tuple(sorted(findings, key=lambda f: (order[f.issue_type], f.drugs))))
