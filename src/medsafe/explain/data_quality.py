"""Plain-English notes for patient values that could not be read.

An unreadable value loads as ``None`` and the patient is kept (docs/DECISIONS.md, D-001). The
record must say so: a ``None`` that came from an unreadable value is a check that could not be
run, never a check that passed. Same principle as an abstained medication name.
"""

from __future__ import annotations

from medsafe.data.schema import Patient

UNREADABLE_NOTES: dict[str, str] = {
    "egfr": "eGFR could not be read; renal checks not verifiable for this patient.",
    "age": "Age could not be read; age-based checks not verifiable for this patient.",
    "weight_kg": "Weight could not be read; weight-based checks not verifiable for this patient.",
    "pregnant": "Pregnancy status could not be read; pregnancy checks not verifiable "
                "for this patient.",
    "row": "The source record was malformed and its values may be misaligned; "
           "verify against the original record.",
}


def data_quality_notes(patient: Patient) -> tuple[str, ...]:
    """One note per unreadable field on ``patient``, in the order the fields failed.

    Returns:
        An empty tuple for a patient whose every value was read as written.
    """
    return tuple(UNREADABLE_NOTES.get(name, f"{name} could not be read; checks that use it "
                                            f"are not verifiable for this patient.")
                 for name in patient.unreadable_fields)
