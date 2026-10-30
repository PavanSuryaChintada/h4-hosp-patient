"""The current regimen: which written lines are medicines the patient is taking now.

Resolution is not the regimen. The resolution file names every line, including medicines marked
stopped. The regimen, which every rule checks, keeps only active medicines:

    active          resolved to one or more generics, not marked stopped
    stopped         a medicine marked stopped, discontinued, omitted or held
    not_a_medicine  resolved to nothing on purpose ("Physiotherapy", "BP charting")
    unresolved      the resolver abstained; it cannot be checked, and says so

A combination brand contributes each of its generics, and every generic keeps the indices of the
entries it came from: the duplicate rules need to know whether two generics share one product.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from medsafe.data.schema import Patient
from medsafe.resolve.resolver import Resolution

# A line the prescriber or nurse marked as no longer taken: stopped, discontinued, withdrawn,
# held, omitted, or "pt not taking since 2 months". "(old Rx)" alone is not one of these: an
# old prescription that is still on the list is still being taken.
STOPPED = re.compile(r"\b(stop|stopped|discontinued|discont|d/c|held|hold|omit|omitted|withdrawn)\b"
                     r"|\bnot\s+taking\b|\bno\s+longer\b", re.IGNORECASE)


def is_stopped(raw: str) -> bool:
    """True if a written line is marked as no longer taken."""
    return bool(STOPPED.search(raw))


@dataclass(frozen=True)
class RegimenEntry:
    """One written line, what it resolved to, and whether it counts as current."""

    index: int
    raw: str
    generics: tuple[str, ...]
    status: str                              # active | stopped | not_a_medicine | unresolved
    confidence: float

    @property
    def active(self) -> bool:
        """True if the rules check this line."""
        return self.status == "active"


@dataclass(frozen=True)
class Regimen:
    """Every written line of one patient, and the generics they are currently taking."""

    entries: tuple[RegimenEntry, ...]

    @property
    def generics(self) -> tuple[str, ...]:
        """Every generic in an active line, sorted, each once."""
        return tuple(sorted({g for e in self.entries if e.active for g in e.generics}))

    def entries_for(self, generic: str) -> tuple[RegimenEntry, ...]:
        """The active lines that contain ``generic``, in list order."""
        return tuple(e for e in self.entries if e.active and generic in e.generics)

    def raw_for(self, generics: Sequence[str]) -> tuple[str, ...]:
        """The written lines behind some generics, in list order, each once."""
        return tuple(e.raw for e in self.entries if e.active and set(e.generics) & set(generics))

    def confidence_for(self, generics: Sequence[str]) -> float:
        """How sure resolution was of the least certain line behind these generics."""
        lines = [e.confidence for e in self.entries if e.active and set(e.generics) & set(generics)]
        return min(lines) if lines else 0.0


def build_regimen(patient: Patient, resolutions: Sequence[Resolution]) -> Regimen:
    """Classify each of a patient's lines and collect the current regimen.

    Args:
        patient: The patient, with medications in list order.
        resolutions: One resolution per medication, same order.
    """
    entries = []
    for medication, resolution in zip(patient.medications, resolutions):
        if resolution.method == "abstained":
            status = "unresolved"
        elif not resolution.generics:
            status = "not_a_medicine"
        elif is_stopped(medication.raw):
            status = "stopped"
        else:
            status = "active"
        entries.append(RegimenEntry(medication.index, medication.raw, resolution.generics, status,
                                    resolution.confidence))
    return Regimen(tuple(entries))
