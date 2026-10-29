"""Plain records the harness scores.

Ground truth is read into these (``eval/truth.py``) and pipeline output is converted into them
(``eval/trace.py``), so the metrics never depend on pipeline internals.
"""

from __future__ import annotations

from dataclasses import dataclass

SERIOUS = frozenset({"high", "medium"})
SEVERITIES = ("high", "medium", "low", "info")


@dataclass(frozen=True)
class Issue:
    """One true issue for one patient."""

    patient_id: str
    issue_type: str                       # interaction | duplicate | renal | contraindication
    drugs: frozenset[str]                 # generics
    severity: str                         # high | medium | low
    rule_id: str = ""
    near_miss: bool = False
    near_miss_reason: str = ""
    raw_drugs: tuple[str, ...] = ()       # the lines on the slip naming these drugs

    @property
    def serious(self) -> bool:
        """True for high and medium severity."""
        return self.severity in SERIOUS


@dataclass(frozen=True)
class Alert:
    """One alert or finding the pipeline raised for one patient.

    ``covers`` lists extra drug sets this alert answers for, for a collapsed alert such as
    "Stop warfarin: clears 4 of the 5 serious interactions". It covers those specific edges,
    not every pair among its drugs.
    """

    patient_id: str
    issue_type: str
    drugs: frozenset[str]
    severity: str
    rule_id: str = ""
    covers: frozenset[frozenset[str]] = frozenset()


@dataclass(frozen=True)
class Resolution:
    """What the pipeline resolved one medication line to. ``resolved`` is None on abstention."""

    patient_id: str
    med_index: int
    resolved: str | None
    method: str                           # exact | fuzzy | abstained


@dataclass(frozen=True)
class TruthMedication:
    """What one medication line really is. ``generic`` is None for a product outside the table."""

    patient_id: str
    med_index: int
    raw: str
    generic: str | None
    mangling: tuple[str, ...]


@dataclass(frozen=True)
class PatientTrace:
    """Everything the harness needs from the pipeline for one loaded patient.

    A stage that is not built yet is None, which the harness reports as "not built" rather than
    "found nothing".
    """

    patient_id: str
    resolutions: tuple[Resolution, ...] | None
    findings: tuple[Alert, ...] | None    # before collapse
    shipped: tuple[Alert, ...] | None     # after collapse and cap: what the output contains
