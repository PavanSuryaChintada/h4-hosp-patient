"""Duplicate therapy, the pack's two cases.

    (a) the same generic in two or more entries (a combination brand plus a single brand, or a
        brand plus its generic name): drugs_involved is that one generic
    (b) two different generics of one duplicate group, written in different entries: drugs
        involved are the two. Components of a single combination product never count against
        each other

Severity is the group's; a drug with no group is moderate; paracetamol from two products is
always major (liver toxicity above 4 g/day).
"""

from __future__ import annotations

from itertools import combinations

from medsafe.rules.regimen import Regimen
from medsafe.rules.tables import RuleTables
from medsafe.rules.types import Finding

NO_GROUP_SEVERITY = "moderate"
PARACETAMOL = "paracetamol"
PARACETAMOL_SEVERITY = "major"


def _severity_and_action(generic: str, group_id: str | None, tables: RuleTables) -> tuple[str, str]:
    """Severity and action for a duplicate within ``group_id`` (None: no group)."""
    group = tables.groups.get(group_id) if group_id else None
    action = (group.action if group and group.action
              else f"{generic} is listed in more than one entry - keep one source")
    if generic == PARACETAMOL:
        return PARACETAMOL_SEVERITY, action
    return (group.severity if group and group.severity else NO_GROUP_SEVERITY), action


def check_duplicates(regimen: Regimen, tables: RuleTables) -> list[Finding]:
    """Same-generic duplicates first, then same-group pairs, each in alphabetical order."""
    findings = []
    for generic in regimen.generics:
        entries = regimen.entries_for(generic)
        if len(entries) >= 2:
            group_id = tables.drug_group.get(generic)
            severity, action = _severity_and_action(generic, group_id, tables)
            findings.append(Finding(
                issue_type="duplicate_therapy", drugs=(generic,), severity=severity, action=action,
                rule_id=f"DUPLICATE_SAME:{generic}",
                evidence={"entries": [e.index for e in entries], "group": group_id},
                raw_drugs=tuple(e.raw for e in entries), confidence=regimen.confidence_for((generic,))))

    by_group: dict[str, list[str]] = {}
    for generic in regimen.generics:
        group_id = tables.drug_group.get(generic)
        if group_id:
            by_group.setdefault(group_id, []).append(generic)
    for group_id, members in sorted(by_group.items()):
        for a, b in combinations(sorted(members), 2):
            in_a = {e.index for e in regimen.entries_for(a)}
            in_b = {e.index for e in regimen.entries_for(b)}
            if any(i != j for i in in_a for j in in_b):
                severity, action = _severity_and_action(a, group_id, tables)
                findings.append(Finding(
                    issue_type="duplicate_therapy", drugs=(a, b), severity=severity, action=action,
                    rule_id=f"DUPLICATE_GROUP:{group_id}:{a}+{b}",
                    evidence={"group": group_id, "entries": sorted(in_a | in_b)},
                    raw_drugs=regimen.raw_for((a, b)), confidence=regimen.confidence_for((a, b))))
    return findings
