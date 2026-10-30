"""Written forms of the conditions the contraindication table uses. Reviewed vocabulary.

Built from TRAINING diagnosis and allergy text only (docs/DECISIONS.md D-024); no test text was
read to write it. Only the 12 diagnosis and 3 allergy condition_ids that drug_disease_
contraindications.csv actually uses are listed: no other condition can change an alert.
Pregnancy comes from the pregnant field, never from text.

Each phrase is matched word by word, tolerating typos (see conditions.py). ABBREVIATIONS match a
whole word exactly, never fuzzily: "PD" is Parkinson's disease, "PDE" is not.
"""

DIAGNOSIS_PHRASES: dict[str, tuple[str, ...]] = {
    "dementia": ("dementia", "alzheimer", "alzheimers"),
    "chronic_liver_disease": ("chronic liver disease", "liver disease", "cirrhosis", "cirrhotic"),
    # Heart failure is often written as reduced heart function: "LVEF 30%", "LV dysfunction",
    # "ischaemic cardiomyopathy (EF 30%)". A normal LVEF is negated by its own clause.
    "heart_failure": ("heart failure", "cardiac failure", "hfref", "hfpef", "lv dysfunction",
                      "lvef", "cardiomyopathy"),
    "peptic_ulcer": ("peptic ulcer", "gastric ulcer", "duodenal ulcer", "ulcer stomach",
                     "stomach ulcer", "gi bleed", "ugi bleed", "upper gi bleed", "melena", "malena"),
    "asthma": ("asthma", "reactive airway"),
    "myasthenia_gravis": ("myasthenia",),
    "angle_closure_glaucoma": ("angle closure glaucoma", "closed angle glaucoma",
                               "narrow angle glaucoma", "angle closure"),
    "gout": ("gout", "gouty", "podagra", "hyperuricemia", "hyperuricaemia"),   # "Gout / hyperuricaemia"
    "parkinsons": ("parkinson", "parkinsons", "parkinsonism", "paralysis agitans"),
    "g6pd_deficiency": ("g6pd",),
    "epilepsy": ("epilepsy", "epileptic", "seizure", "seizures", "convulsive", "convulsion",
                 "convulsions", "fits", "gtcs"),
}

DIAGNOSIS_ABBREVIATIONS: dict[str, str] = {
    "cld": "chronic_liver_disease",
    "hf": "heart_failure", "chf": "heart_failure", "ccf": "heart_failure", "dcmp": "heart_failure",
    "pud": "peptic_ulcer", "du": "peptic_ulcer",
    "ba": "asthma",
    "mg": "myasthenia_gravis",
    "acg": "angle_closure_glaucoma", "pacg": "angle_closure_glaucoma",
    "pd": "parkinsons",
}

ALLERGY_PHRASES: dict[str, tuple[str, ...]] = {
    "penicillin_allergy": ("penicillin", "penicillins", "amoxicillin", "amoxycillin", "augmentin",
                           "amoxiclav", "ampicillin", "cloxacillin"),
    "sulfonamide_allergy": ("sulfa", "sulpha", "sulfonamide", "sulphonamide", "sulfonamides",
                            "sulphonamides", "septran", "bactrim", "cotrimoxazole"),
    "nsaid_hypersensitivity": ("nsaid", "nsaids", "aspirin", "painkiller", "painkillers",
                               "diclofenac", "ibuprofen", "brufen", "voveran", "combiflam"),
}

ALLERGY_ABBREVIATIONS: dict[str, str] = {
    "pcn": "penicillin_allergy",
    "asa": "nsaid_hypersensitivity",
}

# A clause containing one of these states that a condition is absent: "no h/o asthma",
# "PUD ruled out", "tremor - not PD", "penicillin tolerated", "uric acid normal - no gout".
NEGATION_CUES = (r"\bno\b", r"\bnot\b", r"\bnon\b", r"\bnil\b", r"\bnever\b", r"\bdenies\b",
                 r"\bdenied\b", r"\bwithout\b", r"\bnegative\b", r"\bnormal\b", r"\bexcluded\b",
                 r"\btolerated\b", r"\btolerates\b", r"ruled out", r"rule out", r"\br/o\b")
