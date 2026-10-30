"""Confidence-and-limitations text for every alert, and the statement for a patient with none.

The pack requires both on every alert, in every output: how sure we are, which rule fired, what
could not be checked for this patient, that the list may be incomplete, and that a clinician
decides. A patient is never called safe: with no alert, the text says no issue was found in
what was seen.
"""

from __future__ import annotations

from medsafe.data.schema import Patient
from medsafe.rules.regimen import Regimen
from medsafe.rules.types import Finding

DISCLAIMER = "A clinician decides; this system assists and does not prescribe."
INCOMPLETE = "The list may be incomplete."
RULE_SOURCE = {
    "interaction": "interactions.csv",
    "duplicate_therapy": "duplicate_therapy_groups.csv",
    "renal_dose": "renal_rules.csv",
    "contraindication": "drug_disease_contraindications.csv",
}


def not_checked(patient: Patient, regimen: Regimen) -> tuple[str, ...]:
    """What could not be checked for this patient, one plain sentence per gap."""
    gaps = []
    unresolved = [e.raw for e in regimen.entries if e.status == "unresolved"]
    if unresolved:
        gaps.append(f"{len(unresolved)} line(s) could not be identified and were not checked "
                    f"({'; '.join(repr(r) for r in unresolved)}): verify manually")
    if patient.egfr is None:
        reason = "could not be read" if "egfr" in patient.unreadable_fields else "not recorded"
        gaps.append(f"eGFR {reason}: renal checks not verifiable")
    if not patient.diagnoses:
        gaps.append("no diagnoses recorded: condition checks not possible")
    if patient.allergies is None:
        gaps.append("no allergy history recorded: allergy checks not possible")
    if patient.pregnant is None and patient.sex != "M":
        gaps.append("pregnancy status not recorded: pregnancy checks not verifiable")
    for name in patient.unreadable_fields:
        if name not in ("egfr",):
            gaps.append(f"{name.replace('_', ' ')} could not be read")
    return tuple(gaps)


def alert_limitations(finding: Finding, patient: Patient, regimen: Regimen) -> str:
    """The confidence-and-limitations text for one alert."""
    parts = [f"Confidence {finding.confidence:.2f} (how surely the drug names were read).",
             f"Rule {finding.rule_id}, from {RULE_SOURCE[finding.issue_type]}."]
    if "pregnancy_category" in finding.rule_id:
        parts.append("Pregnancy category rule: the reference tables give no action text, so the "
                     "suggested action is a fixed template.")
    gaps = not_checked(patient, regimen)
    parts.append(f"Not checked for this patient: {'; '.join(gaps)}." if gaps
                 else "Every line on the list was identified.")
    parts += [INCOMPLETE, DISCLAIMER]
    return " ".join(parts)


def patient_summary(patient: Patient, regimen: Regimen, alert_count: int) -> str:
    """One line for the top of a patient's record. Never the word safe.

    With alerts, it counts them; with none, it says no issue was found in what was seen.
    """
    medicines = sum(1 for e in regimen.entries if e.status != "not_a_medicine")
    stopped = sum(1 for e in regimen.entries if e.status == "stopped")
    lead = (f"{alert_count} alert(s) in the {medicines} medicines listed." if alert_count
            else f"No issue was found in the {medicines} medicines listed.")
    extra = [f"{stopped} marked stopped were not checked." if stopped else ""]
    gaps = not_checked(patient, regimen)
    if gaps:
        extra.append(f"Not checked: {'; '.join(gaps)}.")
    return " ".join([lead, *filter(None, extra), INCOMPLETE, DISCLAIMER])
