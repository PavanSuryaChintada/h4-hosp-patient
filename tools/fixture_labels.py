"""Issue-level ground truth for the fixtures: what a careful reviewer would flag.

Applies the Round 1 rule logic (ui/src/data/engine.ts) to each patient's TRUE medication list
and TRUE clinical values: the generics that were actually prescribed, and the values as written
before any were blanked. The detector sees the slip as written; this sees what was meant. The
gap between the two is what the evaluation harness measures.

Severity is ``high``, ``medium`` or ``low``; serious means high or medium. Near-misses are a
seeded sample of serious issues that are hard to catch, each with the reason it is hard.
Used only by ``tools/make_fixtures.py``; the pipeline never reads these labels.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import combinations

from fixture_reference import (DRUGS, DUPLICATE_CLASSES, RENAL_THRESHOLDS, RULE_MODIFIER,
                               RefDrug, RefRule, expand_rules)

SERIOUS = ("high", "medium")
N_NEAR_MISSES = 30
HARD_NAME_MANGLINGS = ("misspelled", "squashed")
RENAL_NEAR_THRESHOLD = 10     # eGFR within this many units under a threshold counts as subtle

DRUG_BY_GENERIC: dict[str, RefDrug] = {drug.generic: drug for drug in DRUGS}
PAIR_RULE: dict[frozenset[str], tuple[RefDrug, RefDrug, RefRule]] = {
    frozenset((a.generic, b.generic)): (a, b, rule) for a, b, rule in expand_rules()}


@dataclass(frozen=True)
class Context:
    """A patient's true clinical values, as written before any blanking."""

    age: int
    weight_kg: float
    egfr: int
    pregnant: bool


@dataclass(frozen=True)
class Entry:
    """One medication line: as written, what it really is, and how it was mangled."""

    index: int
    raw: str
    generic: str | None
    mangling: tuple[str, ...]


@dataclass(frozen=True)
class LabelledIssue:
    """One true issue for one patient."""

    patient_id: str
    issue_type: str               # interaction | duplicate | renal | contraindication
    rule_id: str
    drugs: tuple[str, ...]        # generics, sorted
    severity: str                 # high | medium | low
    evidence: str
    raw_drugs: tuple[str, ...]    # every line on the slip naming one of the drugs
    near_miss_reason: str = ""

    @property
    def near_miss(self) -> bool:
        """True if this issue was chosen as a seeded near-miss."""
        return bool(self.near_miss_reason)


def interaction_severity(table_severity: str, modifier: str, ctx: Context) -> tuple[str, str]:
    """Re-score one interaction for the patient, exactly as Round 1 did. Returns (severity, why)."""
    if table_severity == "minor":
        return "low", "table minor"
    if table_severity == "major":
        if modifier == "renal" and ctx.egfr >= 90 and ctx.age < 60:
            return "medium", f"table major; renal rule eased at eGFR {ctx.egfr}, age {ctx.age}"
        return "high", "table major"
    if modifier == "renal" and ctx.egfr < 45:
        return "high", f"table moderate; eGFR {ctx.egfr} < 45"
    if modifier == "bleed" and ctx.age >= 75:
        return "high", f"table moderate; bleeding risk at age {ctx.age}"
    if modifier == "bleed" and ctx.weight_kg < 50:
        return "high", f"table moderate; bleeding risk at {ctx.weight_kg:g} kg"
    if modifier == "cns" and ctx.age >= 65:
        return "high", f"table moderate; CNS depression at age {ctx.age}"
    if modifier == "elderly" and ctx.age >= 75:
        return "high", f"table moderate; age {ctx.age}"
    return "medium", "table moderate"


def label_patient(patient_id: str, ctx: Context, entries: Sequence[Entry]) -> list[LabelledIssue]:
    """Every true issue for one patient, in a stable order."""
    generics = sorted({e.generic for e in entries if e.generic})
    raws = {g: tuple(e.raw for e in entries if e.generic == g) for g in generics}

    def issue(issue_type: str, rule_id: str, drugs: Sequence[str], severity: str,
              evidence: str) -> LabelledIssue:
        """Build one labelled issue, attaching every slip line that names its drugs."""
        drugs = tuple(sorted(drugs))
        return LabelledIssue(patient_id, issue_type, rule_id, drugs, severity, evidence,
                             tuple(raw for g in drugs for raw in raws[g]))

    issues: list[LabelledIssue] = []
    for x, y in combinations(generics, 2):
        hit = PAIR_RULE.get(frozenset((x, y)))
        if hit:
            rule = hit[2]
            severity, why = interaction_severity(rule.severity, RULE_MODIFIER.get(rule.rule_id, ""),
                                                 ctx)
            issues.append(issue("interaction", rule.rule_id, (x, y), severity, why))

    for generic in generics:
        drug = DRUG_BY_GENERIC[generic]
        if drug.code in RENAL_THRESHOLDS:
            reduce, stop = RENAL_THRESHOLDS[drug.code]
            if stop is not None and ctx.egfr < stop:
                issues.append(issue("renal", f"RENAL-{drug.code}", (generic,), "high",
                                    f"eGFR {ctx.egfr} < stop threshold {stop}"))
            elif ctx.egfr < reduce:
                issues.append(issue("renal", f"RENAL-{drug.code}", (generic,),
                                    "high" if ctx.egfr < 30 else "medium",
                                    f"eGFR {ctx.egfr} < reduce threshold {reduce}"))
        if len(raws[generic]) > 1:
            issues.append(issue("duplicate", f"DUP-SAME-{drug.code}", (generic,), "medium",
                                f"{generic} listed {len(raws[generic])} times"))
        if ctx.pregnant and drug.pregnancy:
            issues.append(issue("contraindication", f"PREG-{drug.code}", (generic,),
                                "high" if drug.pregnancy == "avoid" else "medium",
                                f"pregnant; {drug.pregnancy} in pregnancy"))

    for cls in DUPLICATE_CLASSES:
        same = [g for g in generics if DRUG_BY_GENERIC[g].cls == cls]
        if len(same) > 1:
            issues.append(issue("duplicate", f"DUP-CLASS-{cls}", same, "medium",
                                f"{len(same)} drugs of one class"))
    return sorted(issues, key=lambda i: (i.issue_type, i.rule_id, i.drugs))


def near_miss_reason(issue: LabelledIssue, ctx: Context, entries: Sequence[Entry]) -> str:
    """Why a serious issue is easy to miss, or an empty string if it is not subtle."""
    if issue.severity not in SERIOUS:
        return ""
    involved = [e for e in entries if e.generic in issue.drugs]
    for generic in issue.drugs:
        lines = [e for e in involved if e.generic == generic]
        if all(any(m in e.mangling for m in HARD_NAME_MANGLINGS) for e in lines):
            return f"hard-to-read name: '{lines[0].raw}' is {generic}"
    if issue.issue_type == "renal":
        reduce, stop = RENAL_THRESHOLDS[DRUG_BY_GENERIC[issue.drugs[0]].code]
        threshold = stop if stop is not None and ctx.egfr < stop else reduce
        if threshold - ctx.egfr <= RENAL_NEAR_THRESHOLD:
            return f"eGFR {ctx.egfr} is just under the {threshold} threshold"
    if issue.issue_type == "contraindication":
        return f"pregnant, and {issue.drugs[0]} is written as '{involved[0].raw}'"
    if issue.issue_type == "duplicate" and len(issue.drugs) == 1:
        return f"same drug written two ways: {' and '.join(repr(e.raw) for e in involved)}"
    if len(issue.drugs) > 1 and all("brand" in e.mangling for e in involved):
        return f"every drug written as a brand: {' + '.join(repr(e.raw) for e in involved)}"
    return ""


def choose_near_misses(issues: Sequence[LabelledIssue], contexts: dict[str, Context],
                       entries: dict[str, list[Entry]], rng: random.Random,
                       count: int = N_NEAR_MISSES) -> list[LabelledIssue]:
    """Mark a seeded sample of subtle serious issues as near-misses. Returns every issue.

    Sampled round-robin across issue types, so every kind of miss is represented rather than
    whichever type is most common.
    """
    reasons = {i: near_miss_reason(i, contexts[i.patient_id], entries[i.patient_id])
               for i in issues}
    pools: dict[str, list[LabelledIssue]] = {}
    for issue in issues:
        if reasons[issue]:
            pools.setdefault(issue.issue_type, []).append(issue)
    for pool in pools.values():
        rng.shuffle(pool)
    chosen: set[LabelledIssue] = set()
    while len(chosen) < count and any(pools.values()):
        for issue_type in sorted(pools):
            if pools[issue_type] and len(chosen) < count:
                chosen.add(pools[issue_type].pop())
    return [replace(i, near_miss_reason=reasons[i]) if i in chosen else i for i in issues]
