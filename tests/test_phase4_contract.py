"""Blocking contract for Phase 4 (docs/phases/04-context-severity.md R3, docs/DECISIONS.md D-021).

Skips until src/medsafe/explain/context.py exists; from then on Phase 4 cannot land unless it
passes. Unknown never means safe: with age unknown, the age rule must not fire AND the result
must say age is unverifiable, exactly as it does for an unknown eGFR. And the layer only
explains: it has no severity to change.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from medsafe.data.schema import MedicationEntry, Patient

context = pytest.importorskip("medsafe.explain.context")


def patient(age: int | None, egfr: float | None) -> Patient:
    """A patient on warfarin with the given age and eGFR."""
    return Patient("P1", age, "F", 60.0, egfr, False, (), None, (MedicationEntry("Warf 5", 0),), 1)


FINDING = {"issue_type": "interaction", "drugs": ("aspirin", "warfarin"), "severity": "major"}


def test_unknown_age_is_unverifiable_and_never_treated_as_not_elderly() -> None:
    result = context.context_notes(FINDING, patient(age=None, egfr=80.0), FINDING["drugs"])
    assert "age" in result.unverifiable
    assert not any("age" in note.lower() and "anticoagulant" in note.lower() for note in result.notes)


def test_unknown_egfr_is_unverifiable() -> None:
    renal = {"issue_type": "renal_dose", "drugs": ("metformin",), "severity": "major"}
    assert "egfr" in context.context_notes(renal, patient(age=70, egfr=None), renal["drugs"]).unverifiable


def test_context_layer_has_no_severity_to_change() -> None:
    result = context.context_notes(FINDING, patient(age=80, egfr=80.0), FINDING["drugs"])
    assert not any("severity" in f.name for f in fields(result))
