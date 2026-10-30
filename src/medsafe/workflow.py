"""W7-W9, clinician view only: who may do what with an alert, why, and what gets recorded.

The system recommends; a clinician decides. Nothing here applies a change to a prescription, and
nothing here is read by run.py: the predictions file is the same with or without it
(tests/test_compliance.py). The portal enforces these rules and writes these records; this module
is their single source, so the UI hardcodes no policy of its own.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

ROLES = ("prescriber", "pharmacist", "nurse", "lab")
EVENTS = ("shown", "accept", "override", "defer", "escalate")

# What each role may do with an alert. A nurse can see and escalate, never decide. A lab
# technician sees alerts and acts on none: their part is the values the rules read.
PERMISSIONS: dict[str, tuple[str, ...]] = {
    "prescriber": ("accept", "override", "defer"),
    "pharmacist": ("accept", "override", "defer", "escalate"),
    "nurse": ("escalate",),
    "lab": (),
}

# What each role may enter on a patient's record, as on a ward:
#   admit            open a record: age, sex, weight, pregnancy, diagnoses, allergies
#   medication_list  the consolidated list exactly as written from slips, strips and bottles
#   abha_pull        request the patient's records through ABHA; the patient must consent
#   egfr             a lab value; the renal checks re-run on it
#   confirm_name     name the generic(s) on a line the resolver would not guess
# A prescriber decides on alerts and enters no data here.
ENTRIES: dict[str, tuple[str, ...]] = {
    "nurse": ("admit", "medication_list", "abha_pull"),
    "lab": ("egfr",),
    "pharmacist": ("confirm_name",),
    "prescriber": (),
}

# An override must say why. "other" must also say what.
OVERRIDE_REASONS = ("already aware", "intended therapy", "benefit outweighs risk",
                    "patient tolerating", "dose already adjusted", "other")


class NotAllowed(ValueError):
    """An action the role may not take, or an override without a reason."""


@dataclass(frozen=True)
class AuditEvent:
    """One line of the append-only audit log."""

    timestamp: str                  # ISO 8601
    user: str
    role: str
    patient_id: str
    alert: str                      # "issue_type:drug;drug"
    event: str                      # one of EVENTS
    reason: str | None = None       # one of OVERRIDE_REASONS, for an override
    note: str | None = None         # free text; required with reason "other"


def check(event: AuditEvent) -> AuditEvent:
    """Return the event if it is allowed and complete; raise NotAllowed otherwise."""
    if event.role not in ROLES or event.event not in EVENTS:
        raise NotAllowed(f"unknown role {event.role!r} or event {event.event!r}")
    if event.event != "shown" and event.event not in PERMISSIONS[event.role]:
        raise NotAllowed(f"a {event.role} may not {event.event} an alert")
    if event.event == "override":
        if event.reason not in OVERRIDE_REASONS:
            raise NotAllowed(f"an override needs a reason from {OVERRIDE_REASONS}")
        if event.reason == "other" and not (event.note or "").strip():
            raise NotAllowed('an override for "other" needs a note')
    return event


def check_entry(role: str, entry: str) -> None:
    """Raise NotAllowed unless ``role`` may enter ``entry`` on a record (see ENTRIES)."""
    if entry not in ENTRIES.get(role, ()):
        raise NotAllowed(f"a {role} may not enter {entry}")


@dataclass(frozen=True)
class OverridePattern:
    """How often one kind of alert is overridden, and why."""

    issue_type: str
    shown: int
    overridden: int
    reasons: tuple[tuple[str, int], ...]        # most common first

    @property
    def rate(self) -> float:
        """Share of showings that were overridden."""
        return self.overridden / self.shown if self.shown else 0.0


def override_patterns(events: Iterable[AuditEvent]) -> list[OverridePattern]:
    """W9: which kinds of alert get overridden most, and why. Most overridden first.

    This closes the loop: a rule that is overridden for the same reason again and again is a
    rule to review, not a clinician to retrain.
    """
    shown: Counter = Counter()
    overridden: Counter = Counter()
    reasons: dict[str, Counter] = defaultdict(Counter)
    for event in events:
        issue_type = event.alert.split(":", 1)[0]
        if event.event == "shown":
            shown[issue_type] += 1
        elif event.event == "override":
            overridden[issue_type] += 1
            reasons[issue_type][event.reason] += 1
    patterns = [OverridePattern(t, shown[t], overridden[t], tuple(reasons[t].most_common()))
                for t in set(shown) | set(overridden)]
    return sorted(patterns, key=lambda p: (-p.overridden, -p.rate, p.issue_type))
