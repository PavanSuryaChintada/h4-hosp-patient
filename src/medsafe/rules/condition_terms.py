"""Written forms of the conditions the contraindication table uses. Reviewed vocabulary.

Built from TRAINING diagnosis and allergy text only (docs/DECISIONS.md D-024); no test text was
read to write it. Only the 12 diagnosis and 3 allergy condition_ids that drug_disease_
contraindications.csv actually uses are listed: no other condition can change an alert.
Pregnancy comes from the pregnant field, never from text.

Each phrase is matched word by word, tolerating typos (see conditions.py). ABBREVIATIONS match a
whole word exactly, never fuzzily: "PD" is Parkinson's disease, "PDE" is not.

D-027 broadened the training forms by their morphology, never by test text: each training form
also accepts its abbreviation or expansion ("LV dysfunction" -> "LVF", "left ventricular
failure"), its other spellings ("hepatic" for "liver", "bleeding" for "bleed") and its numeric
form ("LVEF 30%" -> any EF below 50%). Every addition is marked "# D-027" below.
"""

DIAGNOSIS_PHRASES: dict[str, tuple[str, ...]] = {
    "dementia": ("dementia", "alzheimer", "alzheimers",
                 "neurocognitive disorder", "lewy body"),                                # D-027
    "chronic_liver_disease": ("chronic liver disease", "liver disease", "cirrhosis", "cirrhotic"),
    # Heart failure is often written as reduced heart function: "LVEF 30%", "LV dysfunction",
    # "ischaemic cardiomyopathy (EF 30%)". A normal LVEF is negated by its own clause, and an EF
    # value is read as a number (conditions.py, EF_HEART_FAILURE_BELOW).
    "heart_failure": ("heart failure", "cardiac failure", "hfref", "hfpef", "lv dysfunction",
                      "lvef", "cardiomyopathy",
                      "hfmref", "lv failure", "left ventricular failure",                   # D-027
                      "left ventricular dysfunction", "lv systolic dysfunction",
                      "reduced ef", "low ef"),
    "peptic_ulcer": ("peptic ulcer", "gastric ulcer", "duodenal ulcer", "ulcer stomach",
                     "stomach ulcer", "gi bleed", "ugi bleed", "upper gi bleed", "melena", "malena",
                     "ulcer duodenum", "bleeding ulcer", "hematemesis", "haematemesis"),     # D-027
    "asthma": ("asthma", "reactive airway",
               "asthmatic"),                                                                 # D-027
    "myasthenia_gravis": ("myasthenia",),
    # "angleclosure" is "angle-closure": words() drops a hyphen inside a word.
    "angle_closure_glaucoma": ("angle closure glaucoma", "closed angle glaucoma",
                               "narrow angle glaucoma", "angle closure",
                               "angleclosure"),                                              # D-027
    "gout": ("gout", "gouty", "podagra", "hyperuricemia", "hyperuricaemia",   # "Gout / hyperuricaemia"
             "tophaceous", "tophi", "tophus",                                                # D-027
             "raised uric acid", "high uric acid", "elevated uric acid"),
    "parkinsons": ("parkinson", "parkinsons", "parkinsonism", "paralysis agitans"),
    "g6pd_deficiency": ("g6pd",
                        "glucose 6 phosphate dehydrogenase",                                 # D-027
                        "glucose6phosphate dehydrogenase"),
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
    # D-027: abbreviations of training phrases, siblings of the training abbreviations above.
    "ald": "chronic_liver_disease",                     # alcoholic liver disease
    "lvf": "heart_failure", "lvsd": "heart_failure",    # LV failure, LV systolic dysfunction
    "icmp": "heart_failure",                            # ischaemic cardiomyopathy, as DCMP
    "ugib": "peptic_ulcer",                             # upper GI bleed
    "aacg": "angle_closure_glaucoma", "cacg": "angle_closure_glaucoma",   # acute / chronic, as PACG
    "ipd": "parkinsons",                                # idiopathic PD
    "g6pdd": "g6pd_deficiency",
    "sz": "epilepsy", "gtc": "epilepsy",                # "SZ" is a training form; GTC(S)
}

# D-027: other ways of writing one word of a phrase. "GI bleeding" is "GI bleed", "hepatic disease"
# is "liver disease", "liver dz" is "liver disease".
WORD_FORMS: dict[str, tuple[str, ...]] = {
    "disease": ("dz", "dis", "disorder"),
    "liver": ("hepatic",),
    "bleed": ("bleeding", "bleeds", "haemorrhage", "hemorrhage"),
    "ulcer": ("ulceration",),
}

# An ejection fraction below this states heart failure (reduced, below 40%, or mildly reduced,
# 41-49%). At or above it the EF is preserved, which alone does not say heart failure. D-027.
EF_HEART_FAILURE_BELOW = 50

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
