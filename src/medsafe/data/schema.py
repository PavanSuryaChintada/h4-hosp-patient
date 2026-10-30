"""Internal schema. Everything downstream speaks these types, never the raw files.

Mirrors the H4 data pack (data/dataset/H4_Medication_Safety_Checker/README.md): one patient
type, one medication-line type, and one type per reference table. The reference tables are
authoritative for this exercise.

Missing values are ``None``, never ``0`` or ``""``. An eGFR of ``None`` means unknown and must
behave differently from an eGFR of ``0``. A value that could not be read is also ``None``, and
its field is named in ``unreadable_fields`` (docs/DECISIONS.md D-001, D-013).
"""

from __future__ import annotations

from dataclasses import dataclass

# The single published severity scale, most severe first. Serious = contraindicated or major.
SEVERITIES = ("contraindicated", "major", "moderate", "minor")
SERIOUS = frozenset({"contraindicated", "major"})
ISSUE_TYPES = ("interaction", "duplicate_therapy", "renal_dose", "contraindication")


@dataclass(frozen=True)
class MedicationEntry:
    """One line of a patient's medication list, exactly as written (split on ';' or line break)."""

    raw: str                 # exactly as written in the source, surrounding spaces trimmed
    index: int               # position in the patient's list, from 0


@dataclass(frozen=True)
class Patient:
    """One patient: clinical context plus the medication list as written."""

    patient_id: str
    age: int | None
    sex: str | None                        # "M" or "F"
    weight_kg: float | None
    egfr: float | None
    pregnant: bool | None                  # None when not applicable (males) or not recorded
    diagnoses: tuple[str, ...]             # free text, split on ';'
    allergies: str | None                  # free text, as written
    medications: tuple[MedicationEntry, ...]
    prescriber_count: int | None
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Drug:
    """One generic in the drug reference, with its single-ingredient brands."""

    generic: str
    drug_id: str | None
    drug_class: str | None
    therapeutic_group: str | None
    duplicate_group: str | None
    brands: tuple[str, ...]
    dose_forms: tuple[str, ...]
    usual_daily_dose: str | None
    max_daily_dose_mg: float | None
    renal_adjust: bool | None
    renal_rule: str | None
    pregnancy_category: str | None         # A, B, C, D, X, or N (not classified here)
    notes: str | None
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class CombinationBrand:
    """A brand that contains two or more generics. One row per strength variant."""

    brand: str
    strength_label: str | None
    dose_form: str | None
    components: str | None                 # with strengths, as written in the table
    generics: tuple[str, ...]              # sorted
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class InteractionPair:
    """One row of the interaction table, between two generics."""

    drug_a: str
    drug_b: str
    severity: str | None                   # as given in the table
    mechanism: str | None
    action: str | None
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenalRule:
    """One eGFR tier for one generic. Applies when eGFR is strictly below ``egfr_below``."""

    generic: str
    egfr_below: int | None
    severity: str | None
    action: str | None
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class DuplicateGroup:
    """A duplicate-therapy group: two members in separate entries are a duplicate."""

    group_id: str
    name: str | None
    severity: str | None
    action: str | None
    members: tuple[str, ...]
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Contraindication:
    """A drug that conflicts with a condition, an allergy, or pregnancy."""

    condition_id: str
    condition_name: str | None
    generic: str
    severity: str | None
    reason: str | None
    action: str | None
    unreadable_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Condition:
    """A condition id used by the contraindication table, with a few example terms."""

    condition_id: str
    name: str | None
    kind: str | None                       # diagnosis, pregnancy_field or allergy
    description: str | None
    example_terms: tuple[str, ...]
    unreadable_fields: tuple[str, ...] = ()
