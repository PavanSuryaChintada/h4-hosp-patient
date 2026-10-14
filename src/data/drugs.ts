// Reference tables. Clinically genuine, commonly cited interactions and renal rules,
// reduced to what the demo cohort needs.

export type Drug = {
  code: string;
  name: string;
  cls: string;
  brands: string[];
  dose: string;
  /** Action used when this drug anchors an interaction cluster. Drugs without it are never suggested for stopping. */
  stop?: string;
  /** Tie-break when two drugs clear the same number of serious interactions. */
  stopRank?: number;
  renal?: { reduce: number; stop?: number; reduceText: string; stopText?: string };
  preg?: { level: 'avoid' | 'caution'; text: string };
};

export const CLASS_LABEL: Record<string, string> = {
  NSAID: 'NSAID', ACEI: 'ACE inhibitor', ARB: 'ARB', KSP: 'potassium-sparing diuretic', LOOP: 'loop diuretic',
  THZ: 'thiazide diuretic', SU: 'sulfonylurea', BIG: 'biguanide', DPP4: 'DPP-4 inhibitor', INS: 'insulin',
  STATIN: 'statin', MACRO: 'macrolide', FQ: 'fluoroquinolone', AZOLE: 'azole antifungal', NITRO: 'nitroimidazole',
  PEN: 'penicillin', ANTICOAG: 'anticoagulant', ANTIPLT: 'antiplatelet', GLYC: 'cardiac glycoside',
  ANTIARR: 'antiarrhythmic', BB: 'beta blocker', CCB: 'calcium channel blocker', PPI: 'proton pump inhibitor',
  ANALG: 'analgesic', OPIOID: 'opioid', BZD: 'benzodiazepine', ZD: 'Z-drug hypnotic', SSRI: 'SSRI',
  TCA: 'tricyclic', GABA: 'gabapentinoid', THY: 'thyroid hormone', XOI: 'xanthine oxidase inhibitor',
  GOUT: 'antigout', STER: 'corticosteroid', DMARD: 'DMARD', AED: 'antiepileptic', ANTIEM: 'antiemetic',
  PROK: 'prokinetic', SUPP: 'supplement', MOOD: 'mood stabiliser', AH: 'antihistamine',
  LTRA: 'leukotriene antagonist', BRONCH: 'bronchodilator', AMAL: 'antimalarial', CAH: 'central antihypertensive',
};

const nsaidRenal = (n: string) => ({
  reduce: 60, stop: 30,
  reduceText: `Limit ${n} to the shortest course: eGFR {e}`,
  stopText: `Stop ${n}: NSAIDs are avoided below eGFR 30`,
});
const rasPreg = (n: string) => ({
  level: 'avoid' as const,
  text: `Stop ${n}: contraindicated in pregnancy. Switch to labetalol or nifedipine`,
});

export const DRUGS: Drug[] = [
  { code: 'WAR', name: 'warfarin', cls: 'ANTICOAG', brands: ['Warf', 'Uniwarfin'], dose: '5 mg OD', preg: { level: 'avoid', text: 'Stop warfarin: teratogenic. Switch to low-molecular-weight heparin' } },
  { code: 'DCF', name: 'diclofenac', cls: 'NSAID', brands: ['Voveran', 'Dynapar', 'Reactin'], dose: '50 mg BD', stop: 'Stop diclofenac', stopRank: 3, renal: nsaidRenal('diclofenac'), preg: { level: 'caution', text: 'Avoid diclofenac after 20 weeks of pregnancy' } },
  { code: 'IBU', name: 'ibuprofen', cls: 'NSAID', brands: ['Brufen', 'Ibugesic'], dose: '400 mg TDS', stop: 'Stop ibuprofen', stopRank: 3, renal: nsaidRenal('ibuprofen') },
  { code: 'ACE', name: 'aceclofenac', cls: 'NSAID', brands: ['Zerodol', 'Hifenac'], dose: '100 mg BD', stop: 'Stop aceclofenac', stopRank: 3, renal: nsaidRenal('aceclofenac') },
  { code: 'NAP', name: 'naproxen', cls: 'NSAID', brands: ['Naprosyn'], dose: '250 mg BD', stop: 'Stop naproxen', stopRank: 3, renal: nsaidRenal('naproxen') },
  { code: 'ASA', name: 'aspirin', cls: 'ANTIPLT', brands: ['Ecosprin', 'Disprin'], dose: '75 mg OD' },
  { code: 'CLO', name: 'clopidogrel', cls: 'ANTIPLT', brands: ['Clopilet', 'Plavix'], dose: '75 mg OD' },
  { code: 'ENA', name: 'enalapril', cls: 'ACEI', brands: ['Envas', 'Enam'], dose: '5 mg OD', preg: rasPreg('enalapril') },
  { code: 'RAM', name: 'ramipril', cls: 'ACEI', brands: ['Cardace', 'Ramistar'], dose: '5 mg OD', preg: rasPreg('ramipril') },
  { code: 'LOS', name: 'losartan', cls: 'ARB', brands: ['Losar', 'Repace'], dose: '50 mg OD', preg: rasPreg('losartan') },
  { code: 'TEL', name: 'telmisartan', cls: 'ARB', brands: ['Telma', 'Telsar'], dose: '40 mg OD', preg: rasPreg('telmisartan') },
  { code: 'SPI', name: 'spironolactone', cls: 'KSP', brands: ['Aldactone'], dose: '25 mg OD' },
  { code: 'FUR', name: 'furosemide', cls: 'LOOP', brands: ['Lasix', 'Frusenex'], dose: '40 mg OD' },
  { code: 'HCT', name: 'hydrochlorothiazide', cls: 'THZ', brands: ['Aquazide'], dose: '12.5 mg OD' },
  { code: 'AML', name: 'amlodipine', cls: 'CCB', brands: ['Amlong', 'Stamlo', 'Amlopres'], dose: '5 mg OD' },
  { code: 'NIF', name: 'nifedipine', cls: 'CCB', brands: ['Depin', 'Nicardia'], dose: '20 mg BD' },
  { code: 'MTF', name: 'metformin', cls: 'BIG', brands: ['Glycomet', 'Glyciphage', 'Obimet'], dose: '500 mg BD', renal: { reduce: 45, stop: 30, reduceText: 'Cap metformin at 1 g/day: eGFR {e} is below 45', stopText: 'Stop metformin: eGFR {e} is below 30' } },
  { code: 'GLM', name: 'glimepiride', cls: 'SU', brands: ['Amaryl', 'Glimy'], dose: '2 mg OD', renal: { reduce: 30, reduceText: 'Drop glimepiride to 1 mg: eGFR {e}' } },
  { code: 'GLB', name: 'glibenclamide', cls: 'SU', brands: ['Daonil'], dose: '5 mg OD', stop: 'Stop glibenclamide', stopRank: 2, renal: { reduce: 60, stop: 60, reduceText: 'Switch glibenclamide to gliclazide: eGFR {e}', stopText: 'Switch glibenclamide to gliclazide: hypoglycaemia risk at eGFR {e}' } },
  { code: 'SIT', name: 'sitagliptin', cls: 'DPP4', brands: ['Januvia', 'Istavel'], dose: '100 mg OD', renal: { reduce: 45, reduceText: 'Halve sitagliptin to 50 mg: eGFR {e}' } },
  { code: 'VIL', name: 'vildagliptin', cls: 'DPP4', brands: ['Galvus', 'Jalra'], dose: '50 mg BD', renal: { reduce: 50, reduceText: 'Halve vildagliptin to 50 mg once daily: eGFR {e}' } },
  { code: 'INS', name: 'insulin glargine', cls: 'INS', brands: ['Lantus', 'Basalog'], dose: '10 units HS' },
  { code: 'ATV', name: 'atorvastatin', cls: 'STATIN', brands: ['Atorva', 'Storvas', 'Lipitor'], dose: '20 mg HS' },
  { code: 'ROS', name: 'rosuvastatin', cls: 'STATIN', brands: ['Rosuvas', 'Crestor'], dose: '10 mg HS' },
  { code: 'SIM', name: 'simvastatin', cls: 'STATIN', brands: ['Simvotin', 'Zocor'], dose: '20 mg HS' },
  { code: 'CLR', name: 'clarithromycin', cls: 'MACRO', brands: ['Claribid'], dose: '500 mg BD', stop: 'Switch clarithromycin to azithromycin', stopRank: 3 },
  { code: 'AZI', name: 'azithromycin', cls: 'MACRO', brands: ['Azithral', 'Azee'], dose: '500 mg OD' },
  { code: 'CIP', name: 'ciprofloxacin', cls: 'FQ', brands: ['Ciplox', 'Cifran'], dose: '500 mg BD', renal: { reduce: 30, reduceText: 'Halve ciprofloxacin: eGFR {e}' } },
  { code: 'LEV', name: 'levofloxacin', cls: 'FQ', brands: ['Levoflox'], dose: '500 mg OD', renal: { reduce: 50, reduceText: 'Give levofloxacin 500 mg every 48 h: eGFR {e}' } },
  { code: 'FLU', name: 'fluconazole', cls: 'AZOLE', brands: ['Forcan', 'Zocon'], dose: '150 mg once', stop: 'Switch fluconazole to topical clotrimazole', stopRank: 2 },
  { code: 'MTZ', name: 'metronidazole', cls: 'NITRO', brands: ['Flagyl', 'Metrogyl'], dose: '400 mg TDS', stop: 'Stop metronidazole', stopRank: 2 },
  { code: 'AMC', name: 'amoxicillin-clavulanate', cls: 'PEN', brands: ['Augmentin', 'Moxikind-CV'], dose: '625 mg BD' },
  { code: 'DIG', name: 'digoxin', cls: 'GLYC', brands: ['Lanoxin'], dose: '0.25 mg OD', renal: { reduce: 50, reduceText: 'Halve digoxin: eGFR {e} slows clearance' } },
  { code: 'AMI', name: 'amiodarone', cls: 'ANTIARR', brands: ['Cordarone'], dose: '200 mg OD' },
  { code: 'MTP', name: 'metoprolol', cls: 'BB', brands: ['Metolar', 'Betaloc', 'Met-XL'], dose: '25 mg BD' },
  { code: 'ATN', name: 'atenolol', cls: 'BB', brands: ['Aten', 'Tenormin'], dose: '25 mg OD', renal: { reduce: 35, reduceText: 'Halve atenolol: eGFR {e}' } },
  { code: 'BIS', name: 'bisoprolol', cls: 'BB', brands: ['Concor'], dose: '5 mg OD' },
  { code: 'PAN', name: 'pantoprazole', cls: 'PPI', brands: ['Pantop', 'Pan', 'Pantocid'], dose: '40 mg OD' },
  { code: 'OME', name: 'omeprazole', cls: 'PPI', brands: ['Omez'], dose: '20 mg OD' },
  { code: 'RAB', name: 'rabeprazole', cls: 'PPI', brands: ['Razo', 'Rablet'], dose: '20 mg OD' },
  { code: 'PCM', name: 'paracetamol', cls: 'ANALG', brands: ['Crocin', 'Dolo', 'Calpol'], dose: '650 mg TDS' },
  { code: 'TRA', name: 'tramadol', cls: 'OPIOID', brands: ['Tramazac', 'Contramal'], dose: '50 mg BD', stop: 'Stop tramadol', stopRank: 2 },
  { code: 'ALP', name: 'alprazolam', cls: 'BZD', brands: ['Alprax', 'Restyl'], dose: '0.25 mg HS', stop: 'Taper alprazolam', stopRank: 2 },
  { code: 'CLZ', name: 'clonazepam', cls: 'BZD', brands: ['Rivotril', 'Clonotril'], dose: '0.5 mg HS', stop: 'Taper clonazepam', stopRank: 2 },
  { code: 'ZOL', name: 'zolpidem', cls: 'ZD', brands: ['Stilnoct', 'Zolfresh'], dose: '5 mg HS', stop: 'Stop zolpidem', stopRank: 3 },
  { code: 'SER', name: 'sertraline', cls: 'SSRI', brands: ['Serta', 'Daxid'], dose: '50 mg OD' },
  { code: 'ESC', name: 'escitalopram', cls: 'SSRI', brands: ['Nexito', 'Cipralex'], dose: '10 mg OD' },
  { code: 'AMT', name: 'amitriptyline', cls: 'TCA', brands: ['Tryptomer'], dose: '10 mg HS' },
  { code: 'PRE', name: 'pregabalin', cls: 'GABA', brands: ['Pregabid', 'Lyrica'], dose: '75 mg BD', renal: { reduce: 60, reduceText: 'Halve pregabalin: eGFR {e}' } },
  { code: 'GAB', name: 'gabapentin', cls: 'GABA', brands: ['Gabapin'], dose: '300 mg TDS', renal: { reduce: 60, reduceText: 'Cut gabapentin to 300 mg/day: eGFR {e}' } },
  { code: 'LTX', name: 'levothyroxine', cls: 'THY', brands: ['Thyronorm', 'Eltroxin'], dose: '50 mcg OD' },
  { code: 'ALL', name: 'allopurinol', cls: 'XOI', brands: ['Zyloric'], dose: '100 mg OD', renal: { reduce: 30, reduceText: 'Cap allopurinol at 100 mg/day: eGFR {e}' } },
  { code: 'COL', name: 'colchicine', cls: 'GOUT', brands: ['Zycolchin'], dose: '0.5 mg BD', renal: { reduce: 30, reduceText: 'Halve colchicine: eGFR {e}' } },
  { code: 'PRD', name: 'prednisolone', cls: 'STER', brands: ['Wysolone', 'Omnacortil'], dose: '10 mg OD' },
  { code: 'MTX', name: 'methotrexate', cls: 'DMARD', brands: ['Folitrax'], dose: '7.5 mg weekly', renal: { reduce: 60, stop: 30, reduceText: 'Halve methotrexate: eGFR {e} slows clearance', stopText: 'Stop methotrexate: eGFR {e} is below 30' }, preg: { level: 'avoid', text: 'Stop methotrexate: teratogenic' } },
  { code: 'HCQ', name: 'hydroxychloroquine', cls: 'AMAL', brands: ['HCQS'], dose: '200 mg OD' },
  { code: 'VAL', name: 'sodium valproate', cls: 'AED', brands: ['Valparin', 'Encorate'], dose: '200 mg BD', preg: { level: 'avoid', text: 'Stop valproate: teratogenic. Refer to neurology today' } },
  { code: 'PHE', name: 'phenytoin', cls: 'AED', brands: ['Eptoin'], dose: '100 mg TDS' },
  { code: 'LIT', name: 'lithium', cls: 'MOOD', brands: ['Licab'], dose: '300 mg BD', renal: { reduce: 60, reduceText: 'Reduce lithium and check level within 1 week: eGFR {e}' } },
  { code: 'DOM', name: 'domperidone', cls: 'PROK', brands: ['Domstal'], dose: '10 mg TDS', stop: 'Stop domperidone', stopRank: 3 },
  { code: 'ODN', name: 'ondansetron', cls: 'ANTIEM', brands: ['Emeset', 'Vomikind'], dose: '4 mg SOS' },
  { code: 'FOL', name: 'folic acid', cls: 'SUPP', brands: ['Folvite'], dose: '5 mg OD' },
  { code: 'FER', name: 'ferrous sulfate', cls: 'SUPP', brands: ['Livogen'], dose: '1 tab OD' },
  { code: 'CAL', name: 'calcium + vitamin D3', cls: 'SUPP', brands: ['Shelcal'], dose: '500 mg BD' },
  { code: 'SAL', name: 'salbutamol', cls: 'BRONCH', brands: ['Asthalin'], dose: '2 puffs SOS' },
  { code: 'MNT', name: 'montelukast', cls: 'LTRA', brands: ['Montair'], dose: '10 mg HS' },
  { code: 'CET', name: 'cetirizine', cls: 'AH', brands: ['Okacet', 'Cetzine'], dose: '10 mg HS' },
  { code: 'LAB', name: 'labetalol', cls: 'BB', brands: ['Labebet'], dose: '100 mg BD' },
];

export const DRUG: Record<string, Drug> = Object.fromEntries(DRUGS.map((d) => [d.code, d]));

export type TableSeverity = 'major' | 'moderate' | 'minor';
/** renal: worse at low eGFR · bleed: worse at age 75+ or weight under 50 kg · cns: worse at age 65+ · elderly: worse at age 75+ */
export type Modifier = '' | 'renal' | 'bleed' | 'cns' | 'elderly';

export type Interaction = {
  id: string;
  a: string; // drug code, or @CLASS
  b: string;
  severity: TableSeverity;
  mod: Modifier;
  mechanism: string;
  action: string; // {a} and {b} are filled with the matched drug names
};

const I = (id: string, a: string, b: string, severity: TableSeverity, mod: Modifier, mechanism: string, action: string): Interaction =>
  ({ id, a, b, severity, mod, mechanism, action });

export const INTERACTIONS: Interaction[] = [
  I('WAR-NSAID-01', 'WAR', '@NSAID', 'major', 'bleed', 'NSAID adds platelet inhibition and gastric erosion to anticoagulation', 'Stop {b}; use paracetamol for pain'),
  I('WAR-ASA-01', 'WAR', 'ASA', 'major', 'bleed', 'Anticoagulant plus antiplatelet: bleeding risk', 'Confirm aspirin is indicated alongside warfarin'),
  I('WAR-CLO-01', 'WAR', 'CLO', 'major', 'bleed', 'Anticoagulant plus antiplatelet: bleeding risk', 'Confirm clopidogrel is indicated alongside warfarin'),
  I('WAR-FLU-01', 'WAR', 'FLU', 'major', '', 'Fluconazole inhibits CYP2C9 and raises INR', 'Switch fluconazole to topical clotrimazole, or check INR within 3 days'),
  I('WAR-MTZ-01', 'WAR', 'MTZ', 'major', '', 'Metronidazole inhibits warfarin metabolism and raises INR', 'Check INR within 3 days of starting metronidazole'),
  I('WAR-CLR-01', 'WAR', 'CLR', 'major', '', 'Clarithromycin inhibits warfarin metabolism and raises INR', 'Check INR within 3 days of starting clarithromycin'),
  I('WAR-AMI-01', 'WAR', 'AMI', 'major', '', 'Amiodarone inhibits CYP2C9 and raises INR', 'Reduce warfarin by a third and check INR weekly'),
  I('WAR-PHE-01', 'WAR', 'PHE', 'major', '', 'Phenytoin alters warfarin metabolism unpredictably', 'Check INR twice weekly until stable'),
  I('WAR-FQ-01', 'WAR', '@FQ', 'moderate', 'bleed', 'Fluoroquinolones raise INR', 'Check INR within 3 days of starting {b}'),
  I('WAR-SSRI-01', 'WAR', '@SSRI', 'moderate', 'bleed', 'SSRIs impair platelet function', 'Check INR at 1 week; watch for bleeding'),
  I('WAR-PRD-01', 'WAR', 'PRD', 'moderate', 'bleed', 'Steroid adds GI bleeding risk and can shift INR', 'Check INR within 1 week; add gastric protection'),
  I('WAR-AMC-01', 'WAR', 'AMC', 'moderate', 'bleed', 'Antibiotic course can raise INR', 'Check INR at the end of the course'),
  I('WAR-PCM-01', 'WAR', 'PCM', 'minor', '', 'Regular paracetamol above 2 g/day can raise INR', 'Keep paracetamol at or below 2 g/day'),

  I('NSAID-ACEI-01', '@NSAID', '@ACEI', 'major', 'renal', 'NSAID reduces renal perfusion under ACE inhibition: acute kidney injury', 'Stop {a}; check creatinine'),
  I('NSAID-ARB-01', '@NSAID', '@ARB', 'major', 'renal', 'NSAID reduces renal perfusion under angiotensin blockade: acute kidney injury', 'Stop {a}; check creatinine'),
  I('NSAID-KSP-01', '@NSAID', 'SPI', 'moderate', 'renal', 'NSAID with potassium-sparing diuretic: hyperkalaemia and renal impairment', 'Stop {a}; check potassium'),
  I('NSAID-LOOP-01', '@NSAID', '@LOOP', 'moderate', 'renal', 'NSAID blunts the diuretic; with an ACE inhibitor it completes the triple-whammy kidney injury pattern', 'Stop {a}; check creatinine'),
  I('NSAID-THZ-01', '@NSAID', '@THZ', 'moderate', 'renal', 'NSAID blunts the diuretic and reduces renal perfusion', 'Stop {a}; check creatinine'),
  I('NSAID-ASA-01', '@NSAID', 'ASA', 'moderate', 'bleed', 'Two NSAID-class agents: GI bleeding, and ibuprofen blocks the antiplatelet effect of aspirin', 'Stop {a}; add gastric protection if both are needed'),
  I('NSAID-CLO-01', '@NSAID', 'CLO', 'moderate', 'bleed', 'NSAID with antiplatelet: GI bleeding', 'Stop {a}; use paracetamol for pain'),
  I('NSAID-PRD-01', '@NSAID', 'PRD', 'moderate', 'bleed', 'NSAID with steroid: GI ulceration', 'Add a proton pump inhibitor, or stop {a}'),
  I('NSAID-MTX-01', '@NSAID', 'MTX', 'major', 'renal', 'NSAID reduces methotrexate clearance: marrow toxicity', 'Stop {a}; check blood count'),
  I('NSAID-LIT-01', '@NSAID', 'LIT', 'major', 'renal', 'NSAID raises lithium levels', 'Stop {a}; check lithium level within 1 week'),
  I('NSAID-SSRI-01', '@NSAID', '@SSRI', 'moderate', 'bleed', 'NSAID with SSRI: GI bleeding', 'Stop {a}, or add a proton pump inhibitor'),

  I('ACEI-KSP-01', '@ACEI', 'SPI', 'major', 'renal', 'ACE inhibitor with potassium-sparing diuretic: hyperkalaemia', 'Check potassium within 1 week'),
  I('ARB-KSP-01', '@ARB', 'SPI', 'major', 'renal', 'ARB with potassium-sparing diuretic: hyperkalaemia', 'Check potassium within 1 week'),
  I('ACEI-ARB-01', '@ACEI', '@ARB', 'major', 'renal', 'Dual renin-angiotensin blockade: hyperkalaemia and kidney injury, no added benefit', 'Stop one of {a} or {b}'),
  I('ACEI-LIT-01', '@ACEI', 'LIT', 'major', 'renal', 'ACE inhibitor reduces lithium clearance', 'Check lithium level within 1 week'),
  I('ARB-LIT-01', '@ARB', 'LIT', 'major', 'renal', 'ARB reduces lithium clearance', 'Check lithium level within 1 week'),
  I('THZ-LIT-01', '@THZ', 'LIT', 'major', 'renal', 'Thiazide reduces lithium clearance', 'Check lithium level within 1 week'),
  I('ACEI-LOOP-01', '@ACEI', '@LOOP', 'minor', '', 'First-dose hypotension', 'Check standing blood pressure'),
  I('ARB-LOOP-01', '@ARB', '@LOOP', 'minor', '', 'First-dose hypotension', 'Check standing blood pressure'),
  I('ARB-THZ-01', '@ARB', '@THZ', 'minor', '', 'Additive blood pressure lowering', 'Check standing blood pressure'),
  I('ACEI-SU-01', '@ACEI', '@SU', 'minor', '', 'ACE inhibitor may enhance hypoglycaemia', 'Advise on hypoglycaemia symptoms'),
  I('ACEI-INS-01', '@ACEI', 'INS', 'minor', '', 'ACE inhibitor may enhance hypoglycaemia', 'Advise on hypoglycaemia symptoms'),
  I('ASA-ACEI-01', 'ASA', '@ACEI', 'minor', '', 'Aspirin at analgesic doses can blunt ACE inhibitor effect', 'No change at 75 mg'),
  I('BB-CCB-01', '@BB', 'AML', 'minor', '', 'Additive blood pressure lowering', 'Check standing blood pressure'),
];

const matches = (ref: string, code: string) =>
  ref.startsWith('@') ? DRUG[code].cls === ref.slice(1) : ref === code;

/** Find the rule for a pair, returning the drugs in rule order. */
export function findInteraction(x: string, y: string): { rule: Interaction; a: string; b: string } | null {
  const sameClass = DRUG[x].cls === DRUG[y].cls;
  for (const rule of INTERACTIONS) {
    if (sameClass && rule.a === rule.b) continue;
    if (matches(rule.a, x) && matches(rule.b, y)) return { rule, a: x, b: y };
    if (matches(rule.a, y) && matches(rule.b, x)) return { rule, a: y, b: x };
  }
  return null;
}

/** How many concrete drug pairs the class-level rules expand to. */
export const EXPANDED_PAIR_COUNT = (() => {
  let n = 0;
  for (let i = 0; i < DRUGS.length; i++)
    for (let j = i + 1; j < DRUGS.length; j++)
      if (findInteraction(DRUGS[i].code, DRUGS[j].code)) n++;
  return n;
})();
