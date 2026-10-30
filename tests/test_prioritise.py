"""W6: ordering and collapse, for the clinician view only."""

from __future__ import annotations

import time

from medsafe.explain.prioritise import collapse, prioritise
from medsafe.rules.types import Finding


def interaction(a: str, b: str, severity: str = "major") -> Finding:
    """An interaction finding between two drugs."""
    return Finding("interaction", tuple(sorted((a, b))), severity, "Review", f"INTERACTION:{a}+{b}")


def test_prioritise_puts_the_most_severe_first() -> None:
    findings = [Finding("duplicate_therapy", ("x",), "moderate", "a", "r1"),
                Finding("renal_dose", ("y",), "major", "a", "r2"),
                interaction("p", "q", "minor"),
                Finding("contraindication", ("z",), "major", "a", "r3"),
                interaction("a", "b", "contraindicated")]
    assert [(f.severity, f.issue_type) for f in prioritise(findings)] == [
        ("contraindicated", "interaction"), ("major", "contraindication"), ("major", "renal_dose"),
        ("moderate", "duplicate_therapy"), ("minor", "interaction")]


def test_one_drug_in_four_of_five_serious_interactions() -> None:
    findings = [interaction("warfarin", d) for d in ("ibuprofen", "aspirin", "fluconazole", "amiodarone")]
    findings.append(interaction("metformin", "contrast"))
    findings.append(interaction("pantoprazole", "iron", "minor"))      # minor never collapses
    result = collapse(findings)
    assert result.drugs == ("warfarin",)
    assert len(result.cleared) == 4 and result.remaining == (("contrast", "metformin"),)
    assert result.summary == "Review warfarin first: involved in 4 of the 5 serious interactions."


def test_no_grouping_when_no_drug_clears_more_than_one() -> None:
    assert collapse([interaction("a", "b"), interaction("c", "d")]) is None
    assert collapse([interaction("a", "b")]) is None
    assert collapse([interaction("a", "b", "moderate"), interaction("a", "c", "moderate")]) is None


def test_collapse_is_deterministic_and_fast() -> None:
    drugs = [f"drug{i:02d}" for i in range(11)]
    findings = [interaction(a, b) for i, a in enumerate(drugs) for b in drugs[i + 1:] if (i + len(b)) % 3 == 0]
    started = time.perf_counter()
    first = collapse(findings)
    assert time.perf_counter() - started < 0.05
    assert collapse(list(reversed(findings))) == first
