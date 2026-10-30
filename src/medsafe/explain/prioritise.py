"""W6, clinician view only: order the alerts, and find the fewest drug changes that clear the most
serious interactions. Never touches the predictions file (docs/DECISIONS.md D-015): the scorer
matches one row per issue, so a collapsed alert there would match nothing.

A patient on nine drugs with five serious interactions often does not have five problems: one
drug can sit in four of the five pairs. Brute force over drug sets of up to three is exact here
(fewer than twelve drugs per patient, at most a few hundred sets) and needs no solver.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import combinations

from medsafe.data.schema import ISSUE_TYPES, SERIOUS
from medsafe.rules.types import SEVERITY_RANK, Finding

ISSUE_ORDER = ("contraindication", "interaction", "renal_dose", "duplicate_therapy")
MAX_SET_SIZE = 3


def prioritise(findings: Iterable[Finding]) -> list[Finding]:
    """Most severe first; within a severity, contraindications, interactions, renal, duplicates;
    then alphabetically by drugs. Deterministic."""
    assert set(ISSUE_ORDER) == set(ISSUE_TYPES)
    return sorted(findings, key=lambda f: (-SEVERITY_RANK[f.severity], ISSUE_ORDER.index(f.issue_type),
                                           f.drugs))


@dataclass(frozen=True)
class Collapse:
    """The smallest drug set whose review clears the most serious interactions."""

    drugs: tuple[str, ...]                              # the drugs to review first
    cleared: tuple[tuple[str, ...], ...]                # interaction pairs those drugs are in
    remaining: tuple[tuple[str, ...], ...]              # serious pairs they do not touch
    total: int                                          # serious interaction pairs in all
    summary: str                                        # e.g. "Review warfarin first: in 4 of the 5 ..."


def collapse(findings: Sequence[Finding], max_set_size: int = MAX_SET_SIZE) -> Collapse | None:
    """The fewest drugs that touch the most serious (contraindicated or major) interactions.

    Every chosen drug must earn its place: it must be in at least two serious pairs that no
    other chosen drug is in. Otherwise "review warfarin and contrast" would beat "review
    warfarin" just by clearing one more pair, which is no grouping at all. Among sets that
    qualify: most pairs cleared, then fewest drugs, then alphabetical. Only interactions
    collapse: a renal or duplicate finding is a different action. Returns None when no drug
    clears two serious pairs, rather than forcing a grouping that helps nobody.
    """
    edges = sorted({f.drugs for f in findings if f.issue_type == "interaction" and f.severity in SERIOUS})
    drugs = sorted({d for edge in edges for d in edge})
    best: tuple[int, tuple[str, ...], list] = (0, (), [])
    for size in range(1, max_set_size + 1):          # smallest sets first, each in alphabetical
        for chosen in combinations(drugs, size):     # order: the first set to clear the most wins
            cleared = [e for e in edges if set(e) & set(chosen)]
            earns_place = all(sum(1 for e in cleared if set(e) & set(chosen) == {d}) >= 2
                              for d in chosen)
            if earns_place and len(cleared) > best[0]:
                best = (len(cleared), chosen, cleared)
    count, chosen, cleared = best
    if not chosen:
        return None
    remaining = [e for e in edges if e not in cleared]
    summary = (f"Review {' and '.join(chosen)} first: involved in {count} of the {len(edges)} "
               f"serious interactions.")
    return Collapse(tuple(chosen), tuple(cleared), tuple(remaining), len(edges), summary)
