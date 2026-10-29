"""Reference tables behind the synthetic fixtures, ported from Round 1 (ui/src/data/drugs.ts).

68 generics with Indian brand names, and 89 interaction rules written at drug or class level
(``@NSAID`` matches every NSAID). The rules are clinically genuine and commonly cited; the
patients built on them are synthetic. Used only by ``tools/make_fixtures.py``.
"""

from __future__ import annotations

from typing import NamedTuple


class RefDrug(NamedTuple):
    """One generic: code, name, class code, brands, typical dose, renal flag, pregnancy level."""

    code: str
    generic: str
    cls: str
    brands: tuple[str, ...]
    dose: str                      # "<amount> <unit> <frequency>"
    renal_adjust: bool
    pregnancy: str | None          # "avoid", "caution" or None


class RefRule(NamedTuple):
    """One interaction rule. ``a``/``b`` are drug codes, or ``@CLASS`` for a whole class."""

    rule_id: str
    a: str
    b: str
    severity: str                  # "major", "moderate" or "minor"
    mechanism: str


CLASS_LABEL: dict[str, str] = {
    "NSAID": "NSAID", "ACEI": "ACE inhibitor", "ARB": "ARB", "KSP": "potassium-sparing diuretic",
    "LOOP": "loop diuretic", "THZ": "thiazide diuretic", "SU": "sulfonylurea",
    "BIG": "biguanide", "DPP4": "DPP-4 inhibitor", "INS": "insulin", "STATIN": "statin",
    "MACRO": "macrolide", "FQ": "fluoroquinolone", "AZOLE": "azole antifungal",
    "NITRO": "nitroimidazole", "PEN": "penicillin", "ANTICOAG": "anticoagulant",
    "ANTIPLT": "antiplatelet", "GLYC": "cardiac glycoside", "ANTIARR": "antiarrhythmic",
    "BB": "beta blocker", "CCB": "calcium channel blocker", "PPI": "proton pump inhibitor",
    "ANALG": "analgesic", "OPIOID": "opioid", "BZD": "benzodiazepine", "ZD": "Z-drug hypnotic",
    "SSRI": "SSRI", "TCA": "tricyclic", "GABA": "gabapentinoid", "THY": "thyroid hormone",
    "XOI": "xanthine oxidase inhibitor", "GOUT": "antigout", "STER": "corticosteroid",
    "DMARD": "DMARD", "AED": "antiepileptic", "ANTIEM": "antiemetic", "PROK": "prokinetic",
    "SUPP": "supplement", "MOOD": "mood stabiliser", "AH": "antihistamine",
    "LTRA": "leukotriene antagonist", "BRONCH": "bronchodilator", "AMAL": "antimalarial",
}


def _d(code: str, generic: str, cls: str, brands: tuple[str, ...], dose: str,
       renal: bool = False, pregnancy: str | None = None) -> RefDrug:
    """Shorthand constructor for the table below."""
    return RefDrug(code, generic, cls, brands, dose, renal, pregnancy)


DRUGS: tuple[RefDrug, ...] = (
    _d("WAR", "warfarin", "ANTICOAG", ("Warf", "Uniwarfin"), "5 mg OD", pregnancy="avoid"),
    _d("DCF", "diclofenac", "NSAID", ("Voveran", "Dynapar", "Reactin"), "50 mg BD", True, "caution"),
    _d("IBU", "ibuprofen", "NSAID", ("Brufen", "Ibugesic"), "400 mg TDS", True),
    _d("ACE", "aceclofenac", "NSAID", ("Zerodol", "Hifenac"), "100 mg BD", True),
    _d("NAP", "naproxen", "NSAID", ("Naprosyn",), "250 mg BD", True),
    _d("ASA", "aspirin", "ANTIPLT", ("Ecosprin", "Disprin"), "75 mg OD"),
    _d("CLO", "clopidogrel", "ANTIPLT", ("Clopilet", "Plavix"), "75 mg OD"),
    _d("ENA", "enalapril", "ACEI", ("Envas", "Enam"), "5 mg OD", pregnancy="avoid"),
    _d("RAM", "ramipril", "ACEI", ("Cardace", "Ramistar"), "5 mg OD", pregnancy="avoid"),
    _d("LOS", "losartan", "ARB", ("Losar", "Repace"), "50 mg OD", pregnancy="avoid"),
    _d("TEL", "telmisartan", "ARB", ("Telma", "Telsar"), "40 mg OD", pregnancy="avoid"),
    _d("SPI", "spironolactone", "KSP", ("Aldactone",), "25 mg OD"),
    _d("FUR", "furosemide", "LOOP", ("Lasix", "Frusenex"), "40 mg OD"),
    _d("HCT", "hydrochlorothiazide", "THZ", ("Aquazide",), "12.5 mg OD"),
    _d("AML", "amlodipine", "CCB", ("Amlong", "Stamlo", "Amlopres"), "5 mg OD"),
    _d("NIF", "nifedipine", "CCB", ("Depin", "Nicardia"), "20 mg BD"),
    _d("MTF", "metformin", "BIG", ("Glycomet", "Glyciphage", "Obimet"), "500 mg BD", True),
    _d("GLM", "glimepiride", "SU", ("Amaryl", "Glimy"), "2 mg OD", True),
    _d("GLB", "glibenclamide", "SU", ("Daonil",), "5 mg OD", True),
    _d("SIT", "sitagliptin", "DPP4", ("Januvia", "Istavel"), "100 mg OD", True),
    _d("VIL", "vildagliptin", "DPP4", ("Galvus", "Jalra"), "50 mg BD", True),
    _d("INS", "insulin glargine", "INS", ("Lantus", "Basalog"), "10 units HS"),
    _d("ATV", "atorvastatin", "STATIN", ("Atorva", "Storvas", "Lipitor"), "20 mg HS"),
    _d("ROS", "rosuvastatin", "STATIN", ("Rosuvas", "Crestor"), "10 mg HS"),
    _d("SIM", "simvastatin", "STATIN", ("Simvotin", "Zocor"), "20 mg HS"),
    _d("CLR", "clarithromycin", "MACRO", ("Claribid",), "500 mg BD"),
    _d("AZI", "azithromycin", "MACRO", ("Azithral", "Azee"), "500 mg OD"),
    _d("CIP", "ciprofloxacin", "FQ", ("Ciplox", "Cifran"), "500 mg BD", True),
    _d("LEV", "levofloxacin", "FQ", ("Levoflox",), "500 mg OD", True),
    _d("FLU", "fluconazole", "AZOLE", ("Forcan", "Zocon"), "150 mg once"),
    _d("MTZ", "metronidazole", "NITRO", ("Flagyl", "Metrogyl"), "400 mg TDS"),
    _d("AMC", "amoxicillin-clavulanate", "PEN", ("Augmentin", "Moxikind-CV"), "625 mg BD"),
    _d("DIG", "digoxin", "GLYC", ("Lanoxin",), "0.25 mg OD", True),
    _d("AMI", "amiodarone", "ANTIARR", ("Cordarone",), "200 mg OD"),
    _d("MTP", "metoprolol", "BB", ("Metolar", "Betaloc", "Met-XL"), "25 mg BD"),
    _d("ATN", "atenolol", "BB", ("Aten", "Tenormin"), "25 mg OD", True),
    _d("BIS", "bisoprolol", "BB", ("Concor",), "5 mg OD"),
    _d("PAN", "pantoprazole", "PPI", ("Pantop", "Pan", "Pantocid"), "40 mg OD"),
    _d("OME", "omeprazole", "PPI", ("Omez",), "20 mg OD"),
    _d("RAB", "rabeprazole", "PPI", ("Razo", "Rablet"), "20 mg OD"),
    _d("PCM", "paracetamol", "ANALG", ("Crocin", "Dolo", "Calpol"), "650 mg TDS"),
    _d("TRA", "tramadol", "OPIOID", ("Tramazac", "Contramal"), "50 mg BD"),
    _d("ALP", "alprazolam", "BZD", ("Alprax", "Restyl"), "0.25 mg HS"),
    _d("CLZ", "clonazepam", "BZD", ("Rivotril", "Clonotril"), "0.5 mg HS"),
    _d("ZOL", "zolpidem", "ZD", ("Stilnoct", "Zolfresh"), "5 mg HS"),
    _d("SER", "sertraline", "SSRI", ("Serta", "Daxid"), "50 mg OD"),
    _d("ESC", "escitalopram", "SSRI", ("Nexito", "Cipralex"), "10 mg OD"),
    _d("AMT", "amitriptyline", "TCA", ("Tryptomer",), "10 mg HS"),
    _d("PRE", "pregabalin", "GABA", ("Pregabid", "Lyrica"), "75 mg BD", True),
    _d("GAB", "gabapentin", "GABA", ("Gabapin",), "300 mg TDS", True),
    _d("LTX", "levothyroxine", "THY", ("Thyronorm", "Eltroxin"), "50 mcg OD"),
    _d("ALL", "allopurinol", "XOI", ("Zyloric",), "100 mg OD", True),
    _d("COL", "colchicine", "GOUT", ("Zycolchin",), "0.5 mg BD", True),
    _d("PRD", "prednisolone", "STER", ("Wysolone", "Omnacortil"), "10 mg OD"),
    _d("MTX", "methotrexate", "DMARD", ("Folitrax",), "7.5 mg weekly", True, "avoid"),
    _d("HCQ", "hydroxychloroquine", "AMAL", ("HCQS",), "200 mg OD"),
    _d("VAL", "sodium valproate", "AED", ("Valparin", "Encorate"), "200 mg BD", pregnancy="avoid"),
    _d("PHE", "phenytoin", "AED", ("Eptoin",), "100 mg TDS"),
    _d("LIT", "lithium", "MOOD", ("Licab",), "300 mg BD", True),
    _d("DOM", "domperidone", "PROK", ("Domstal",), "10 mg TDS"),
    _d("ODN", "ondansetron", "ANTIEM", ("Emeset", "Vomikind"), "4 mg SOS"),
    _d("FOL", "folic acid", "SUPP", ("Folvite",), "5 mg OD"),
    _d("FER", "ferrous sulfate", "SUPP", ("Livogen",), "1 tab OD"),
    _d("CAL", "calcium + vitamin D3", "SUPP", ("Shelcal",), "500 mg BD"),
    _d("SAL", "salbutamol", "BRONCH", ("Asthalin",), "2 puffs SOS"),
    _d("MNT", "montelukast", "LTRA", ("Montair",), "10 mg HS"),
    _d("CET", "cetirizine", "AH", ("Okacet", "Cetzine"), "10 mg HS"),
    _d("LAB", "labetalol", "BB", ("Labebet",), "100 mg BD"),
)

DRUG_BY_CODE: dict[str, RefDrug] = {drug.code: drug for drug in DRUGS}

_R = RefRule
RULES: tuple[RefRule, ...] = (
    _R("WAR-NSAID-01", "WAR", "@NSAID", "major", "NSAID adds platelet inhibition and gastric erosion to anticoagulation"),
    _R("WAR-ASA-01", "WAR", "ASA", "major", "Anticoagulant plus antiplatelet: bleeding risk"),
    _R("WAR-CLO-01", "WAR", "CLO", "major", "Anticoagulant plus antiplatelet: bleeding risk"),
    _R("WAR-FLU-01", "WAR", "FLU", "major", "Fluconazole inhibits CYP2C9 and raises INR"),
    _R("WAR-MTZ-01", "WAR", "MTZ", "major", "Metronidazole inhibits warfarin metabolism and raises INR"),
    _R("WAR-CLR-01", "WAR", "CLR", "major", "Clarithromycin inhibits warfarin metabolism and raises INR"),
    _R("WAR-AMI-01", "WAR", "AMI", "major", "Amiodarone inhibits CYP2C9 and raises INR"),
    _R("WAR-PHE-01", "WAR", "PHE", "major", "Phenytoin alters warfarin metabolism unpredictably"),
    _R("WAR-FQ-01", "WAR", "@FQ", "moderate", "Fluoroquinolones raise INR"),
    _R("WAR-SSRI-01", "WAR", "@SSRI", "moderate", "SSRIs impair platelet function"),
    _R("WAR-PRD-01", "WAR", "PRD", "moderate", "Steroid adds GI bleeding risk and can shift INR"),
    _R("WAR-AMC-01", "WAR", "AMC", "moderate", "Antibiotic course can raise INR"),
    _R("WAR-PCM-01", "WAR", "PCM", "minor", "Regular paracetamol above 2 g/day can raise INR"),

    _R("NSAID-ACEI-01", "@NSAID", "@ACEI", "major", "NSAID reduces renal perfusion under ACE inhibition: acute kidney injury"),
    _R("NSAID-ARB-01", "@NSAID", "@ARB", "major", "NSAID reduces renal perfusion under angiotensin blockade: acute kidney injury"),
    _R("NSAID-KSP-01", "@NSAID", "SPI", "moderate", "NSAID with potassium-sparing diuretic: hyperkalaemia and renal impairment"),
    _R("NSAID-LOOP-01", "@NSAID", "@LOOP", "moderate", "NSAID blunts the diuretic; with an ACE inhibitor it completes the triple-whammy kidney injury pattern"),
    _R("NSAID-THZ-01", "@NSAID", "@THZ", "moderate", "NSAID blunts the diuretic and reduces renal perfusion"),
    _R("NSAID-ASA-01", "@NSAID", "ASA", "moderate", "Two NSAID-class agents: GI bleeding, and ibuprofen blocks the antiplatelet effect of aspirin"),
    _R("NSAID-CLO-01", "@NSAID", "CLO", "moderate", "NSAID with antiplatelet: GI bleeding"),
    _R("NSAID-PRD-01", "@NSAID", "PRD", "moderate", "NSAID with steroid: GI ulceration"),
    _R("NSAID-MTX-01", "@NSAID", "MTX", "major", "NSAID reduces methotrexate clearance: marrow toxicity"),
    _R("NSAID-LIT-01", "@NSAID", "LIT", "major", "NSAID raises lithium levels"),
    _R("NSAID-SSRI-01", "@NSAID", "@SSRI", "moderate", "NSAID with SSRI: GI bleeding"),

    _R("ACEI-KSP-01", "@ACEI", "SPI", "major", "ACE inhibitor with potassium-sparing diuretic: hyperkalaemia"),
    _R("ARB-KSP-01", "@ARB", "SPI", "major", "ARB with potassium-sparing diuretic: hyperkalaemia"),
    _R("ACEI-ARB-01", "@ACEI", "@ARB", "major", "Dual renin-angiotensin blockade: hyperkalaemia and kidney injury, no added benefit"),
    _R("ACEI-LIT-01", "@ACEI", "LIT", "major", "ACE inhibitor reduces lithium clearance"),
    _R("ARB-LIT-01", "@ARB", "LIT", "major", "ARB reduces lithium clearance"),
    _R("THZ-LIT-01", "@THZ", "LIT", "major", "Thiazide reduces lithium clearance"),
    _R("ACEI-LOOP-01", "@ACEI", "@LOOP", "minor", "First-dose hypotension"),
    _R("ARB-LOOP-01", "@ARB", "@LOOP", "minor", "First-dose hypotension"),
    _R("ARB-THZ-01", "@ARB", "@THZ", "minor", "Additive blood pressure lowering"),
    _R("ACEI-SU-01", "@ACEI", "@SU", "minor", "ACE inhibitor may enhance hypoglycaemia"),
    _R("ACEI-INS-01", "@ACEI", "INS", "minor", "ACE inhibitor may enhance hypoglycaemia"),
    _R("ASA-ACEI-01", "ASA", "@ACEI", "minor", "Aspirin at analgesic doses can blunt ACE inhibitor effect"),
    _R("BB-CCB-01", "@BB", "AML", "minor", "Additive blood pressure lowering"),

    _R("MTF-LOOP-01", "MTF", "@LOOP", "minor", "Furosemide may raise metformin levels"),
    _R("MTF-PRD-01", "MTF", "PRD", "minor", "Steroid raises blood glucose"),
    _R("SU-PRD-01", "@SU", "PRD", "moderate", "Steroid raises blood glucose"),
    _R("SU-CLR-01", "@SU", "CLR", "moderate", "Clarithromycin raises sulfonylurea levels: hypoglycaemia"),
    _R("SU-FLU-01", "@SU", "FLU", "moderate", "Fluconazole raises sulfonylurea levels: hypoglycaemia"),
    _R("SU-FQ-01", "@SU", "@FQ", "moderate", "Fluoroquinolones cause unpredictable glucose swings"),
    _R("SU-BB-01", "@SU", "@BB", "minor", "Beta blocker can mask hypoglycaemia"),
    _R("SU-THZ-01", "@SU", "@THZ", "minor", "Thiazide raises blood glucose"),

    _R("CLR-SIM-01", "CLR", "SIM", "major", "CYP3A4 inhibition raises simvastatin: myopathy"),
    _R("CLR-ATV-01", "CLR", "ATV", "major", "CYP3A4 inhibition raises atorvastatin: myopathy"),
    _R("CLR-AML-01", "CLR", "AML", "moderate", "Clarithromycin raises amlodipine levels: hypotension"),
    _R("CLR-DIG-01", "CLR", "DIG", "major", "Clarithromycin raises digoxin levels: toxicity"),
    _R("CLR-COL-01", "CLR", "COL", "major", "Clarithromycin raises colchicine levels: toxicity"),
    _R("CLR-DOM-01", "CLR", "DOM", "major", "Additive QT prolongation"),
    _R("AMI-DIG-01", "AMI", "DIG", "major", "Amiodarone raises digoxin levels"),
    _R("AMI-SIM-01", "AMI", "SIM", "major", "Amiodarone raises simvastatin: myopathy"),
    _R("AMI-ATV-01", "AMI", "ATV", "moderate", "Amiodarone raises atorvastatin levels"),
    _R("AMI-BB-01", "AMI", "@BB", "moderate", "Bradycardia and heart block"),
    _R("AMI-AZI-01", "AMI", "AZI", "major", "Additive QT prolongation"),
    _R("AMI-LEV-01", "AMI", "LEV", "major", "Additive QT prolongation"),
    _R("DIG-LOOP-01", "DIG", "@LOOP", "moderate", "Loop-diuretic hypokalaemia potentiates digoxin toxicity"),
    _R("FLU-SIM-01", "FLU", "SIM", "major", "Fluconazole raises simvastatin: myopathy"),
    _R("FLU-ATV-01", "FLU", "ATV", "moderate", "Fluconazole raises atorvastatin levels"),
    _R("FLU-DOM-01", "FLU", "DOM", "major", "Additive QT prolongation"),

    _R("BZD-OPI-01", "@BZD", "@OPIOID", "major", "Combined CNS and respiratory depression"),
    _R("BZD-ZD-01", "@BZD", "@ZD", "major", "Two sedative hypnotics: additive sedation and falls"),
    _R("ZD-OPI-01", "@ZD", "@OPIOID", "major", "Additive CNS depression and falls"),
    _R("BZD-GABA-01", "@BZD", "@GABA", "moderate", "Additive sedation and falls"),
    _R("BZD-TCA-01", "@BZD", "@TCA", "moderate", "Additive sedation and anticholinergic load"),
    _R("ZD-TCA-01", "@ZD", "@TCA", "moderate", "Additive sedation and falls"),
    _R("OPI-GABA-01", "@OPIOID", "@GABA", "moderate", "Additive respiratory depression"),
    _R("OPI-SSRI-01", "@OPIOID", "@SSRI", "major", "Tramadol with SSRI: serotonin syndrome and seizures"),
    _R("OPI-TCA-01", "@OPIOID", "@TCA", "major", "Tramadol with tricyclic: serotonin syndrome and seizures"),
    _R("TCA-SSRI-01", "@TCA", "@SSRI", "moderate", "SSRI raises tricyclic levels; additive serotonergic effect"),
    _R("SSRI-ASA-01", "@SSRI", "ASA", "moderate", "SSRI with aspirin: GI bleeding"),
    _R("SSRI-CLO-01", "@SSRI", "CLO", "moderate", "SSRI with clopidogrel: bleeding"),
    _R("ASA-CLO-01", "ASA", "CLO", "moderate", "Dual antiplatelet therapy: bleeding"),
    _R("ASA-PRD-01", "ASA", "PRD", "moderate", "Aspirin with steroid: GI ulceration"),
    _R("CLO-OME-01", "CLO", "OME", "moderate", "Omeprazole reduces clopidogrel activation"),

    _R("LTX-CAL-01", "LTX", "CAL", "minor", "Calcium reduces levothyroxine absorption"),
    _R("LTX-FER-01", "LTX", "FER", "minor", "Iron reduces levothyroxine absorption"),
    _R("LTX-PPI-01", "LTX", "@PPI", "minor", "Acid suppression can reduce levothyroxine absorption"),
    _R("PPI-FER-01", "@PPI", "FER", "minor", "Acid suppression reduces iron absorption"),
    _R("CAL-FER-01", "CAL", "FER", "minor", "Calcium reduces iron absorption"),
    _R("MTX-PPI-01", "MTX", "@PPI", "minor", "PPI can slow methotrexate clearance"),
    _R("FQ-PRD-01", "@FQ", "PRD", "moderate", "Fluoroquinolone with steroid: tendon rupture"),
    _R("ESC-DOM-01", "ESC", "DOM", "moderate", "Additive QT prolongation"),
    _R("ODN-ESC-01", "ODN", "ESC", "moderate", "Additive QT prolongation"),
    _R("ODN-DOM-01", "ODN", "DOM", "moderate", "Additive QT prolongation"),
    _R("PHE-VAL-01", "PHE", "VAL", "moderate", "Valproate displaces phenytoin and inhibits its metabolism"),
    _R("BB-SAL-01", "@BB", "SAL", "moderate", "Beta blocker can blunt the bronchodilator response"),
    _R("AML-SIM-01", "AML", "SIM", "minor", "Amlodipine raises simvastatin levels"),
)


def _matches(ref: str, drug: RefDrug) -> bool:
    """True if a rule side (drug code or ``@CLASS``) matches ``drug``."""
    return drug.cls == ref[1:] if ref.startswith("@") else drug.code == ref


def expand_rules() -> list[tuple[RefDrug, RefDrug, RefRule]]:
    """Expand class-level rules into concrete generic pairs, exactly as Round 1 did.

    Every unordered pair of drugs takes the first rule that matches it, with the drugs returned
    in the rule's order. Round 1 reports 195 pairs from these 89 rules.
    """
    pairs = []
    for i, x in enumerate(DRUGS):
        for y in DRUGS[i + 1:]:
            for rule in RULES:
                if x.cls == y.cls and rule.a == rule.b:
                    continue
                if _matches(rule.a, x) and _matches(rule.b, y):
                    pairs.append((x, y, rule))
                    break
                if _matches(rule.a, y) and _matches(rule.b, x):
                    pairs.append((y, x, rule))
                    break
    return pairs
