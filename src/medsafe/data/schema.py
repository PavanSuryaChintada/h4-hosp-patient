"""Internal schema. Frozen: everything downstream speaks these types, never the raw files.

Missing values are ``None``, never ``0`` or ``""``. An eGFR of ``None`` means unknown and
must behave differently from an eGFR of ``0``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MedicationEntry:
    """One line of a patient's medication list, exactly as written."""

    raw: str                 # exactly as written in the source
    index: int               # position in the patient's list


@dataclass(frozen=True)
class Patient:
    """One patient: clinical context plus the medication list as written.

    ``unreadable_fields`` names the fields whose source value failed validation and was loaded
    as ``None``, so a downstream stage can tell "could not be read" from "not recorded". Neither
    is ever treated as safe (docs/DECISIONS.md).
    """

    patient_id: str
    age: int | None
    weight_kg: float | None
    egfr: float | None
    pregnant: bool | None
    diagnoses: tuple[str, ...]
    medications: tuple[MedicationEntry, ...]
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Drug:
    """One generic in the reference table, with the brand names it is sold under."""

    generic: str
    drug_class: str
    brands: tuple[str, ...]
    renal_adjust: bool
    pregnancy_category: str | None


@dataclass(frozen=True)
class InteractionPair:
    """One row of the interaction table, between two generics."""

    drug_a: str              # generic
    drug_b: str              # generic
    severity: str            # as given in the source table
    mechanism: str | None
