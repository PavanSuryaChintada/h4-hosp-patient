"""R7-R11: free-text diagnoses and allergies -> condition_ids, with negation scoped to a clause.

Every false positive here is a full noise unit, a precision hit and a wrong severity, so the
negation cases matter as much as the positive ones.
"""

from __future__ import annotations

import pytest

from conftest import requires_pack
from medsafe.rules.conditions import clauses, detect_conditions


def present(*diagnoses: str, allergies: str | None = None) -> set[str]:
    """Conditions found present."""
    return set(detect_conditions(diagnoses, allergies).present)


@pytest.mark.parametrize(("text", "condition"), [
    ("B. asthma", "asthma"), ("BA", "asthma"), ("wheezy since childhood - asthma", "asthma"),
    ("reactive airway disease", "asthma"), ("astthma", "asthma"),
    ("h/o UGI bleed", "peptic_ulcer"), ("melena 2023 - PUD", "peptic_ulcer"),
    ("gastric ulcer (2023)", "peptic_ulcer"), ("bleeding DU (2022)", "peptic_ulcer"),
    ("LVEF 30%", "heart_failure"), ("DCMP", "heart_failure"), ("HFrEF (EF 35%)", "heart_failure"),
    ("ischaemic cardiomyopathy (EF 30%)", "heart_failure"), ("caridac failure", "heart_failure"),
    ("CLD - ascites", "chronic_liver_disease"), ("cirrhoosis", "chronic_liver_disease"),
    ("alcoholic liver disease", "chronic_liver_disease"),
    ("memory loss - deementia", "dementia"), ("Alzheimer's", "dementia"),
    ("Parkinson's", "parkinsons"), ("paralysis agitans", "parkinsons"), ("PD", "parkinsons"),
    ("ocular myastenia", "myasthenia_gravis"), ("PACG", "angle_closure_glaucoma"),
    ("anle closure glaucoma", "angle_closure_glaucoma"), ("hypeeruricemia", "gout"),
    ("podagra (gout)", "gout"), ("G-6-PD deficiency", "g6pd_deficiency"),
    ("fits since childhood", "epilepsy"), ("GTCS on AED", "epilepsy"),
])
def test_condition_is_found(text: str, condition: str) -> None:
    assert condition in present(text)


@pytest.mark.parametrize("text", [
    "no h/o asthma", "asthma ruled out", "PUD ruled out", "no h/o PUD", "no GI bleed",
    "tremor - not PD", "no parkinsonism", "uric acid normal - no gout", "LVEF normal - no HF",
    "LFT normal, no liver disease", "no dementia", "memory normal", "no fits",
    "no h/o seizures", "denies asthma", "r/o epilepsy",
])
def test_negated_condition_is_not_present(text: str) -> None:
    assert present(text) == set()


def test_negation_stays_in_its_own_clause() -> None:
    assert present("no h/o asthma; acute bronchitis") == set()
    assert present("no h/o asthma; PUD") == {"peptic_ulcer"}
    assert present("asthma ruled out", "B. asthma") == {"asthma"}       # stated present elsewhere
    assert clauses("LFT normal, no liver disease") == ["LFT normal", "no liver disease"]


@pytest.mark.parametrize("text", [
    "acid peptic disease", "gastritis", "APD", "chronic hep B", "HBsAg +ve", "CKD 3b",
    "COPD - ex smoker", "chronic bronchitis", "HTN since 10 yrs", "madhumeh (DM)", "",
])
def test_conditions_the_table_does_not_use_change_nothing(text: str) -> None:
    """Gastritis is not a peptic ulcer, hepatitis B is not cirrhosis, CKD text is never read."""
    assert present(text) == set()


@pytest.mark.parametrize(("allergies", "condition"), [
    ("amoxicillin - hives", "penicillin_allergy"), ("PCN allergy", "penicillin_allergy"),
    ("allergic to Augmentin", "penicillin_allergy"), ("Septran - SJS", "sulfonamide_allergy"),
    ("co-trimoxazole rash (sulfa)", "sulfonamide_allergy"),
    ("brufen - swelling (NSAID)", "nsaid_hypersensitivity"),
    ("ASA sensitive asthma", "nsaid_hypersensitivity"),
    ("painkiller allergy (diclofenac - angioedema)", "nsaid_hypersensitivity"),
])
def test_allergy_is_found(allergies: str, condition: str) -> None:
    assert present(allergies=allergies) == {condition}


@pytest.mark.parametrize("allergies", [
    "NKDA", "nil", "No known allergy", "NKA", "No drug allergy (penicillin tolerated)",
    "no sulfa allergy", "NKDA - took aspirin before without problem",
])
def test_no_allergy_means_nothing(allergies: str) -> None:
    assert present(allergies=allergies) == set()


def test_diagnosis_text_never_yields_an_allergy_and_vice_versa() -> None:
    assert present("aspirin allergy") == set()
    assert present(allergies="asthma") == set()


@requires_pack
def test_matcher_agrees_with_the_back_derived_truth(pack_train) -> None:
    """R7: every condition the labels prove present is found; none they prove absent is."""
    import sys
    from conftest import REPO_ROOT
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from derive_condition_truth import derive
    from eval.pack import data_dir
    from eval.truth import load_truth
    from medsafe.pipeline import run_pipeline
    result = run_pipeline(pack_train)
    proven_present, proven_absent, _ = derive(pack_train, load_truth(data_dir()).issues, result)
    found = {(p.patient.patient_id, c) for p in result.patients for c in p.rules.conditions.present}
    assert proven_present - found == set()
    assert proven_absent & found == set()
    assert len(proven_present) >= 80 and len(proven_absent) >= 3000
