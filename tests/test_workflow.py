"""W7-W9: who may act on an alert, why an override must say why, and the override patterns."""

from __future__ import annotations

import pytest

from medsafe.workflow import (OVERRIDE_REASONS, PERMISSIONS, AuditEvent, NotAllowed, check,
                              override_patterns)


def event(role: str, kind: str, reason: str | None = None, note: str | None = None,
          alert: str = "interaction:ibuprofen;warfarin") -> AuditEvent:
    """An audit event at a fixed time."""
    return AuditEvent("2026-10-30T10:00:00Z", "dr.rao", role, "H4P-MINI0001", alert, kind, reason, note)


@pytest.mark.parametrize(("role", "kind", "allowed"), [
    ("prescriber", "accept", True), ("prescriber", "override", True), ("prescriber", "escalate", False),
    ("pharmacist", "accept", True), ("pharmacist", "escalate", True),
    ("nurse", "escalate", True), ("nurse", "accept", False), ("nurse", "override", False),
    ("nurse", "shown", True),
])
def test_role_permissions(role: str, kind: str, allowed: bool) -> None:
    reason = OVERRIDE_REASONS[0] if kind == "override" else None
    if allowed:
        assert check(event(role, kind, reason))
    else:
        with pytest.raises(NotAllowed):
            check(event(role, kind, reason))


def test_an_override_must_say_why() -> None:
    with pytest.raises(NotAllowed, match="reason"):
        check(event("prescriber", "override"))
    with pytest.raises(NotAllowed, match="note"):
        check(event("prescriber", "override", "other"))
    assert check(event("prescriber", "override", "other", "short course, INR checked"))
    assert set(OVERRIDE_REASONS) >= {"already aware", "intended therapy", "benefit outweighs risk",
                                     "patient tolerating", "dose already adjusted", "other"}
    assert "accept" not in PERMISSIONS["nurse"]


def test_override_patterns_show_what_is_overridden_most_and_why() -> None:
    log = [event("prescriber", "shown"), event("prescriber", "override", "intended therapy"),
           event("prescriber", "shown"), event("prescriber", "override", "intended therapy"),
           event("prescriber", "shown"), event("prescriber", "accept"),
           event("prescriber", "shown", alert="renal_dose:metformin"),
           event("pharmacist", "override", "dose already adjusted", alert="renal_dose:metformin")]
    patterns = override_patterns(log)
    assert [(p.issue_type, p.shown, p.overridden) for p in patterns] == [
        ("interaction", 3, 2), ("renal_dose", 1, 1)]
    assert patterns[0].reasons == (("intended therapy", 2),)
    assert patterns[1].rate == 1.0
