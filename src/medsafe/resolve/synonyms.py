"""Curated written forms that are not in the drug tables: abbreviations and name variants.

General prescribing knowledge (PCM is paracetamol, frusemide is the British name for
furosemide), not memorised patient strings. An entry whose generic is missing from the drug
reference is dropped when the index is built, and listed in its ``dropped_synonyms``.
"""

SYNONYMS: dict[str, tuple[str, ...]] = {
    # Abbreviations common on Indian prescriptions
    "pcm": ("paracetamol",),
    "mtx": ("methotrexate",),
    "ismn": ("isosorbide mononitrate",),
    "isdn": ("isosorbide dinitrate",),
    "hcq": ("hydroxychloroquine",),
    "hcqs": ("hydroxychloroquine",),
    "hctz": ("hydrochlorothiazide",),
    "ntg": ("nitroglycerin",),
    "gtn": ("nitroglycerin",),
    "kcl": ("potassium chloride",),
    "udca": ("ursodeoxycholic acid",),
    "sod bicarb": ("sodium bicarbonate",),
    "soda bicarb": ("sodium bicarbonate",),
    "sodium bicarb": ("sodium bicarbonate",),
    # Name variants
    "acetaminophen": ("paracetamol",),
    "mecobalamin": ("methylcobalamin",),     # not "vitamin B12": cyanocobalamin is listed too
    "vitamin d3": ("cholecalciferol",),
    "vit d3": ("cholecalciferol",),
    "vitamin d": ("cholecalciferol",),
    "vit d": ("cholecalciferol",),
    "thyroxine": ("levothyroxine",),
    "l thyroxine": ("levothyroxine",),
    "thyroxine sodium": ("levothyroxine",),
    "levothyroxine sodium": ("levothyroxine",),
    "frusemide": ("furosemide",),
    "glyburide": ("glibenclamide",),
    "albuterol": ("salbutamol",),
    "l dopa": ("levodopa",),
    "rifampin": ("rifampicin",),
    "amoxyclav": ("amoxicillin", "clavulanic acid"),
    "amoxiclav": ("amoxicillin", "clavulanic acid"),
    "co amoxiclav": ("amoxicillin", "clavulanic acid"),
    "cotrimoxazole": ("sulfamethoxazole", "trimethoprim"),
    "co trimoxazole": ("sulfamethoxazole", "trimethoprim"),
    "tmp smx": ("sulfamethoxazole", "trimethoprim"),
    "smx tmp": ("sulfamethoxazole", "trimethoprim"),
    # Premixed human insulin: the ratio names the regular/isophane mix
    "insulin 30/70": ("insulin isophane", "insulin regular"),
    "insulin 50/50": ("insulin isophane", "insulin regular"),
}

# Short forms that only name a generic inside a combination ("calcium + D3", "montelukast-LC").
# On their own they are too ambiguous to resolve.
COMBO_PART_SYNONYMS: dict[str, tuple[str, ...]] = {
    "d3": ("cholecalciferol",),
    "lc": ("levocetirizine",),
    "calcium": ("calcium carbonate",),
}

# Words that mark a line as not a medicine: devices, monitoring, tests, diet, follow-up.
# Checked only after an exact name match has failed, so a real brand always wins.
NON_DRUG_WORDS = frozenset({
    "charting", "chart", "collar", "check", "diet", "advice", "dressing", "ecg", "echo",
    "strips", "strip", "glucometer", "fomentation", "needles", "needle", "syringe", "syringes",
    "knee", "belt", "brace", "nebulisation", "nebulization", "physiotherapy", "physio",
    "fluids", "monitoring", "monitor", "rft", "lft", "cbc", "review", "visit", "followup",
    "restriction", "steam", "walker", "crutches", "exercise", "exercises", "yoga", "walking",
    "counselling", "counseling", "test", "tests", "labs", "bandage", "splint", "stockings",
    "cushion", "mattress", "done",
})
