"""Generate the synthetic fixtures the pipeline is built and tested against.

    python tools/make_fixtures.py [--out tests/fixtures]

Deterministic from ``SEED``: the same command always writes the same bytes. Writes four files:

    patients.csv       200 patients: age, weight, eGFR, pregnancy, diagnoses, medication list
    drugs.csv          68 generics: class, brand names, renal flag, pregnancy level
    interactions.csv   195 generic pairs: table severity and mechanism
    ground_truth.csv   the true generic behind every medication string, and how it was mangled

Medication strings are written the way a real slip looks: brand and generic mixed, form prefixes
(``T.``, ``Tab``, ``Cap``, ``Inj``), strengths with and without units, release qualifiers,
frequency suffixes, misspellings, squashed spacing, and the odd product that is not in the
reference table at all. Some clinical values are left blank, because real records have gaps.

The adapter never reads ``ground_truth.csv``. Phase 2 uses it to measure resolution accuracy.
"""

from __future__ import annotations

import argparse
import csv
import random
from collections.abc import Sequence
from pathlib import Path

from fixture_reference import CLASS_LABEL, DRUG_BY_CODE, DRUGS, RefDrug, expand_rules

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tests" / "fixtures"

SEED = 2026
N_PATIENTS = 200
MIN_MEDS, MAX_MEDS = 4, 12
EGFR_MIN, EGFR_MAX = 15, 110

PREGNANT_RATE = 0.08
ELDERLY_RATE = 0.25           # share of non-pregnant patients aged 76-92
OUT_OF_REFERENCE_RATE = 0.10  # patients with one product not in the drug table
REPEAT_RATE = 0.08            # patients with the same generic written twice
MAX_FILLERS = 2               # drugs outside the patient's profiles, to keep lists coherent
BLANK_RATE = {"age": 0.03, "weight_kg": 0.06, "egfr": 0.04, "pregnant": 0.03}

LIST_SEPARATOR = "|"          # must match medsafe.data.adapter.LIST_SEPARATOR

# Clinical profile -> (diagnoses, drug codes a patient with it is likely to be on).
PROFILES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "cardiometabolic": (("Type 2 diabetes", "Hypertension", "Dyslipidaemia"),
                        ("MTF", "GLM", "GLB", "SIT", "VIL", "INS", "TEL", "LOS", "ENA", "RAM",
                         "AML", "HCT", "ATV", "ROS", "ASA")),
    "hypertension": (("Hypertension",), ("TEL", "LOS", "ENA", "RAM", "AML", "NIF", "HCT", "ATN")),
    "af_heart_failure": (("Atrial fibrillation", "Heart failure"),
                         ("WAR", "AMI", "DIG", "MTP", "BIS", "FUR", "SPI", "RAM", "ENA", "ATV")),
    "coronary": (("Ischaemic heart disease", "Dyslipidaemia"),
                 ("ASA", "CLO", "ATV", "ROS", "SIM", "MTP", "BIS", "RAM", "PAN", "OME")),
    "arthritis_pain": (("Osteoarthritis", "Chronic back pain"),
                       ("DCF", "IBU", "ACE", "NAP", "PCM", "TRA", "PAN", "PRE", "GAB", "CAL")),
    "psych_sleep": (("Depression", "Insomnia", "Anxiety"),
                    ("SER", "ESC", "AMT", "ALP", "CLZ", "ZOL")),
    "respiratory_infection": (("COPD", "Lower respiratory infection"),
                              ("SAL", "MNT", "PRD", "AZI", "CLR", "LEV", "CIP", "AMC", "CET")),
    "gout_ckd": (("Gout", "Chronic kidney disease"), ("ALL", "COL", "FUR", "NIF", "ATN", "CAL")),
    "rheumatoid": (("Rheumatoid arthritis",), ("MTX", "HCQ", "FOL", "PRD", "NAP", "PAN")),
    "epilepsy_mood": (("Epilepsy", "Bipolar disorder"), ("VAL", "PHE", "LIT", "CLZ")),
    "gi_infection": (("Acid reflux", "Gastroenteritis"),
                     ("PAN", "OME", "RAB", "DOM", "ODN", "MTZ", "CIP", "FLU")),
    "thyroid": (("Hypothyroidism",), ("LTX", "CAL", "FER", "OME")),
    "pregnancy": (("Pregnancy",), ("FOL", "FER", "CAL", "LAB", "NIF", "PCM", "ODN")),
}

# Relative odds of each profile, by age group. Pregnancy is assigned separately.
PROFILE_WEIGHTS = {
    "older": {"cardiometabolic": 5, "hypertension": 3, "af_heart_failure": 3, "coronary": 3,
              "arthritis_pain": 3, "psych_sleep": 2, "respiratory_infection": 2, "gout_ckd": 2,
              "rheumatoid": 1, "epilepsy_mood": 1, "gi_infection": 2, "thyroid": 1},
    "younger": {"cardiometabolic": 2, "hypertension": 2, "af_heart_failure": 0.5, "coronary": 1,
                "arthritis_pain": 2, "psych_sleep": 3, "respiratory_infection": 2, "gout_ckd": 1,
                "rheumatoid": 2, "epilepsy_mood": 2, "gi_infection": 3, "thyroid": 2},
}
PREGNANCY_COMPANIONS = ("hypertension", "epilepsy_mood", "thyroid", "psych_sleep")

# Real products a slip may carry that are not in the 68-drug reference table.
OUT_OF_REFERENCE = ("Becosules", "Neurobion Forte", "Limcee 500", "Evion 400", "Digene",
                    "Cremaffin syrup", "Zincovit", "Revital H")

FORM_PREFIXES = ("T.", "T ", "Tab", "Tab.", "Cap", "Cap.")
RELEASE_QUALIFIERS = ("SR", "XR", "ER", "CR", "DS")
FREQUENCY_STYLES = {"OD": ("OD", "1-0-0"), "BD": ("BD", "1-0-1"), "TDS": ("TDS", "1-1-1"),
                    "HS": ("HS", "0-0-1")}
STRENGTH_UNITS = ("mg", "mcg")
VOWELS = "aeiou"

PATIENT_COLUMNS = ("patient_id", "age", "weight_kg", "egfr", "pregnant", "diagnoses",
                   "medications")
DRUG_COLUMNS = ("generic", "drug_class", "brands", "renal_adjust", "pregnancy_category")
INTERACTION_COLUMNS = ("drug_a", "drug_b", "severity", "mechanism")
TRUTH_COLUMNS = ("patient_id", "med_index", "raw", "true_generic", "mangling")


def misspell(word: str, rng: random.Random) -> str:
    """Introduce one handwriting-style error: a dropped, swapped, doubled or wrong vowel letter.

    The first letter is never touched; on a slip it is the most legible one.
    """
    for _ in range(10):
        letters = [i for i in range(1, len(word)) if word[i].isalpha()]
        if not letters:
            return word
        i = rng.choice(letters)
        operation = rng.choice(("drop", "swap", "double", "vowel"))
        if operation == "drop":
            candidate = word[:i] + word[i + 1:]
        elif operation == "swap" and i + 1 < len(word) and word[i + 1].isalpha():
            candidate = word[:i] + word[i + 1] + word[i] + word[i + 2:]
        elif operation == "double":
            candidate = word[:i] + word[i] + word[i:]
        elif operation == "vowel" and word[i].lower() in VOWELS:
            replacement = rng.choice([v for v in VOWELS if v != word[i].lower()])
            candidate = word[:i] + replacement + word[i + 1:]
        else:
            continue
        if candidate != word:
            return candidate
    return word


def render_medication(drug: RefDrug, rng: random.Random) -> tuple[str, list[str]]:
    """Write one drug the way a prescriber might, returning the string and the manglings used."""
    if rng.random() < 0.6:
        name, tags = rng.choice(drug.brands), ["brand"]
    else:
        name, tags = rng.choice((drug.generic, drug.generic.capitalize())), ["generic"]

    if len(name) >= 5 and rng.random() < 0.18:
        name, tags = misspell(name, rng), tags + ["misspelled"]
    if drug.cls in {"BIG", "BB", "SU", "CCB", "GABA"} and rng.random() < 0.12:
        name = f"{name}{rng.choice(('-', ' '))}{rng.choice(RELEASE_QUALIFIERS)}"
        tags.append("release")

    amount, unit, frequency = drug.dose.split(" ", 2)
    style = rng.random()
    if unit not in STRENGTH_UNITS or style < 0.15:
        text = name
    elif style < 0.50:
        text, tags = f"{name} {amount}", tags + ["strength"]
    elif style < 0.75:
        text = f"{name} {amount}{rng.choice(('', ' '))}{unit}"
        tags.append("strength_unit")
    elif style < 0.88:
        written = rng.choice(FREQUENCY_STYLES.get(frequency, (frequency,)))
        text, tags = f"{name} {amount} {unit} {written}", tags + ["frequency"]
    else:
        text, tags = f"{name}{amount}", tags + ["squashed"]

    if drug.code == "INS" and rng.random() < 0.7:
        text, tags = f"Inj {text}", tags + ["form_prefix"]
    elif drug.code == "SAL" and rng.random() < 0.5:
        text, tags = f"{text} inhaler", tags + ["form_suffix"]
    elif drug.code not in {"INS", "SAL"} and rng.random() < 0.25:
        text, tags = f"{rng.choice(FORM_PREFIXES)} {text}".replace("  ", " "), tags + ["form_prefix"]

    case = rng.random()
    if case < 0.12:
        text, tags = text.lower(), tags + ["lowercase"]
    elif case < 0.18:
        text, tags = text.upper(), tags + ["uppercase"]
    return text.strip(), tags


def choose_profiles(age: int, pregnant: bool, rng: random.Random) -> list[str]:
    """Pick the clinical profiles that shape one patient's diagnoses and medicines."""
    if pregnant:
        profiles = ["pregnancy"]
        if rng.random() < 0.5:
            profiles.append(rng.choice(PREGNANCY_COMPANIONS))
        return profiles
    weights = PROFILE_WEIGHTS["older" if age >= 60 else "younger"]
    wanted = rng.choice((1, 2, 2, 2, 3))
    profiles: list[str] = []
    while len(profiles) < wanted:
        pick = rng.choices(list(weights), weights=list(weights.values()))[0]
        if pick not in profiles:
            profiles.append(pick)
    return profiles


def make_patient(number: int, rng: random.Random) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Generate one patient row and the ground-truth rows for its medication list."""
    patient_id = f"P{number:04d}"
    pregnant = rng.random() < PREGNANT_RATE
    if pregnant:
        age = rng.randint(20, 40)
    elif rng.random() < ELDERLY_RATE:
        age = rng.randint(76, 92)
    else:
        age = rng.randint(18, 75)

    profiles = choose_profiles(age, pregnant, rng)
    diagnoses: list[str] = []
    pool: list[str] = []
    for profile in profiles:
        names, codes = PROFILES[profile]
        diagnoses += [d for d in rng.sample(names, rng.randint(1, len(names))) if d not in diagnoses]
        pool += [code for code in codes if code not in pool]

    has_unknown = rng.random() < OUT_OF_REFERENCE_RATE
    has_repeat = rng.random() < REPEAT_RATE
    extras = int(has_unknown) + int(has_repeat)
    total = rng.randint(MIN_MEDS, min(MAX_MEDS, len(pool) + MAX_FILLERS + extras))
    n_reference = total - extras
    codes = rng.sample(pool, min(n_reference, len(pool)))
    if len(codes) < n_reference:
        fillers = [drug.code for drug in DRUGS if drug.code not in codes]
        codes += rng.sample(fillers, n_reference - len(codes))

    entries: list[tuple[str, str | None, list[str]]] = []
    for code in codes:
        raw, tags = render_medication(DRUG_BY_CODE[code], rng)
        entries.append((raw, DRUG_BY_CODE[code].generic, tags))
    if has_repeat:
        drug = DRUG_BY_CODE[rng.choice(codes)]
        raw, tags = render_medication(drug, rng)
        entries.append((raw, drug.generic, tags + ["repeat"]))
    if has_unknown:
        entries.append((rng.choice(OUT_OF_REFERENCE), None, ["out_of_reference"]))
    rng.shuffle(entries)

    egfr = rng.gauss(128 - 0.95 * age, 12) - (30 if "gout_ckd" in profiles else 0)
    weight = rng.gauss(62, 8) if pregnant else rng.gauss(64, 12)
    weight = min(max(weight, 38), 115)
    row = {
        "patient_id": patient_id,
        "age": str(age),
        "weight_kg": f"{weight:.1f}" if rng.random() < 0.3 else str(round(weight)),
        "egfr": str(round(min(max(egfr, EGFR_MIN), EGFR_MAX))),
        "pregnant": "Y" if pregnant else "N",
        "diagnoses": LIST_SEPARATOR.join(diagnoses),
        "medications": LIST_SEPARATOR.join(raw for raw, _, _ in entries),
    }
    for field, rate in BLANK_RATE.items():
        if rng.random() < rate and not (field == "pregnant" and pregnant):
            row[field] = ""

    truth = [{"patient_id": patient_id, "med_index": str(index), "raw": raw,
              "true_generic": generic or "", "mangling": "+".join(tags)}
             for index, (raw, generic, tags) in enumerate(entries)]
    return row, truth


def drug_rows() -> list[dict[str, str]]:
    """The drug reference table as CSV rows."""
    return [{"generic": drug.generic, "drug_class": CLASS_LABEL[drug.cls],
             "brands": LIST_SEPARATOR.join(drug.brands),
             "renal_adjust": "Y" if drug.renal_adjust else "N",
             "pregnancy_category": drug.pregnancy or ""} for drug in DRUGS]


def interaction_rows() -> list[dict[str, str]]:
    """The interaction table as CSV rows, one per concrete generic pair."""
    return [{"drug_a": a.generic, "drug_b": b.generic, "severity": rule.severity,
             "mechanism": rule.mechanism} for a, b, rule in expand_rules()]


def write_csv(path: Path, columns: Sequence[str], rows: list[dict[str, str]]) -> None:
    """Write rows with LF line endings so output bytes are identical on every OS."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate(out_dir: Path) -> dict[str, int]:
    """Write all four fixture files into ``out_dir``. Returns headline counts."""
    rng = random.Random(SEED)
    patients, truth = [], []
    for number in range(1, N_PATIENTS + 1):
        row, rows = make_patient(number, rng)
        patients.append(row)
        truth += rows

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "patients.csv", PATIENT_COLUMNS, patients)
    write_csv(out_dir / "drugs.csv", DRUG_COLUMNS, drug_rows())
    write_csv(out_dir / "interactions.csv", INTERACTION_COLUMNS, interaction_rows())
    write_csv(out_dir / "ground_truth.csv", TRUTH_COLUMNS, truth)

    egfrs = [int(p["egfr"]) for p in patients if p["egfr"]]
    return {
        "patients": len(patients),
        "medication_entries": len(truth),
        "misspelled": sum("misspelled" in t["mangling"] for t in truth),
        "brand_written": sum(t["mangling"].startswith("brand") for t in truth),
        "out_of_reference": sum(not t["true_generic"] for t in truth),
        "pregnant": sum(p["pregnant"] == "Y" for p in patients),
        "over_75": sum(bool(p["age"]) and int(p["age"]) > 75 for p in patients),
        "egfr_below_30": sum(e < 30 for e in egfrs),
        "egfr_min": min(egfrs),
        "egfr_max": max(egfrs),
        **{f"blank_{field}": sum(not p[field] for p in patients) for field in BLANK_RATE},
    }


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args(argv)
    counts = generate(args.out)
    print(f"wrote fixtures to {args.out}")
    for name, value in counts.items():
        print(f"  {name:<20} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
