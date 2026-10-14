// Simulated cohort. Medication lists are written the way a real slip looks:
// mixed brand and generic, misspellings, dose suffixes.

export type Method = 'exact' | 'fuzzy' | 'abstained';

export type MedEntry = {
  raw: string;
  code: string | null; // resolved generic, null when abstained
  confidence: number;
  method: Method;
  /** Ground truth from the generator, when it differs from what was resolved. */
  truth?: string;
  /** Top candidates for an abstention. */
  candidates?: [string, number][];
};

export type Patient = {
  id: string;
  age: number;
  sex: 'F' | 'M';
  weight: number;
  egfr: number;
  pregnant: boolean;
  dx: string[];
  meds: MedEntry[];
};

const e = (raw: string, code: string, confidence: number): MedEntry => ({ raw, code, confidence, method: 'exact' });
const f = (raw: string, code: string, confidence: number, truth?: string): MedEntry => ({ raw, code, confidence, method: 'fuzzy', truth });

const P = (id: string, age: number, sex: 'F' | 'M', weight: number, egfr: number, dx: string[], meds: MedEntry[], pregnant = false): Patient =>
  ({ id, age, sex, weight, egfr, pregnant, dx, meds });

export const PATIENTS: Patient[] = [
  P('2270', 81, 'F', 48, 38, ['Hypertension', 'Insomnia', 'Osteoarthritis', 'Anxiety'], [
    e('Alprax 0.25', 'ALP', 0.98), f('zolfresh5', 'ZOL', 0.9), e('Tramazac 50', 'TRA', 0.96),
    f('amlong 5mg', 'AML', 0.94), e('Calpol 500', 'PCM', 0.97), f('pantop 40', 'PAN', 0.93),
  ]),
  P('2271', 67, 'M', 72, 64, ['Type 2 diabetes', 'Hypertension', 'Dyslipidaemia'], [
    e('Glycomet 500', 'MTF', 0.99), e('Amaryl 2', 'GLM', 0.98), f('Telma40', 'TEL', 0.95),
    e('Atorva 20', 'ATV', 0.98), f('Tab Ecosprin', 'ASA', 0.94),
  ]),
  P('2272', 72, 'M', 66, 52, ['Atrial fibrillation', 'Heart failure', 'Hypertension'], [
    e('Cordarone 200', 'AMI', 0.98), e('Lanoxin 0.25', 'DIG', 0.98), f('Warf 3', 'WAR', 0.91),
    e('Metolar 25', 'MTP', 0.97), e('Lasix 40', 'FUR', 0.99), f('rosuvastatn 10', 'ROS', 0.9),
  ]),
  P('2273', 45, 'F', 58, 98, ['Hypothyroidism', 'Migraine'], [
    f('Thyronrm 75', 'LTX', 0.92), e('Naprosyn 250', 'NAP', 0.97), e('Domstal 10', 'DOM', 0.97),
    e('Pantocid 40', 'PAN', 0.98),
  ]),
  P('2274', 78, 'M', 60, 41, ['COPD', 'Type 2 diabetes', 'Hypertension', 'Lower respiratory infection'], [
    e('Asthalin inhaler', 'SAL', 0.98), e('Montair 10', 'MNT', 0.98), e('Glycomet-SR 500', 'MTF', 0.97),
    f('wysolon 10', 'PRD', 0.89), e('Levoflox 500', 'LEV', 0.97), e('Cardace 5', 'RAM', 0.96),
  ]),
  P('2275', 34, 'M', 70, 105, ['Acid reflux', 'Allergic rhinitis'], [
    f('Raz 20', 'RAB', 0.86), e('Okacet', 'CET', 0.97), e('Montair 10', 'MNT', 0.98), e('Calpol 650', 'PCM', 0.97),
  ]),
  P('2276', 69, 'F', 55, 47, ['Rheumatoid arthritis', 'Hypertension', 'GERD'], [
    e('Folitrax 7.5', 'MTX', 0.97), f('zerodl 100', 'ACE', 0.88), e('Omez 20', 'OME', 0.97),
    e('HCQS 200', 'HCQ', 0.98), e('Wysolone 5', 'PRD', 0.98), f('folvit 5', 'FOL', 0.93),
  ]),
  P('2277', 63, 'M', 74, 34, ['Type 2 diabetes', 'CKD stage 3b', 'Hypertension'], [
    e('Januvia 100', 'SIT', 0.99), f('lantus 10 units', 'INS', 0.95), e('Losar 50', 'LOS', 0.98),
    e('Amlong 5', 'AML', 0.98), f('Rosuvas10', 'ROS', 0.94),
  ]),
  P('2278', 55, 'F', 64, 88, ['Depression', 'Chronic back pain', 'Hypertension'], [
    e('Nexito 10', 'ESC', 0.98), f('tramazc 50', 'TRA', 0.9), e('Tryptomer 10', 'AMT', 0.97),
    e('Telma 40', 'TEL', 0.99), f('pantoprazol 40', 'PAN', 0.95),
  ]),
  P('2279', 82, 'F', 45, 31, ['Atrial fibrillation', 'Hypertension', 'Urinary tract infection', 'Vaginal candidiasis'], [
    e('Uniwarfin 2', 'WAR', 0.97), e('Ciplox 500', 'CIP', 0.98), e('Forcan 150', 'FLU', 0.97),
    f('Atn 25', 'ATN', 0.84), e('Pan 40', 'PAN', 0.95),
  ]),
  P('2280', 61, 'M', 78, 80, ['Type 2 diabetes', 'Hypertension'], [
    e('Glycomet 500', 'MTF', 0.99), e('Amlong 5', 'AML', 0.98), f('atorvastatin 10mg', 'ATV', 0.97),
    e('Envas 5', 'ENA', 0.96),
  ]),
  P('2281', 70, 'M', 70, 58, ['Coronary artery disease', 'Type 2 diabetes', 'Dyslipidaemia', 'GERD'], [
    e('Ecosprin 75', 'ASA', 0.98), e('Clopilet 75', 'CLO', 0.98), f('omez20', 'OME', 0.94),
    e('Storvas 40', 'ATV', 0.97), f('glimy 2mg', 'GLM', 0.92), e('Metolar 50', 'MTP', 0.97),
  ]),
  P('2282', 76, 'F', 52, 44, ['Hypertension', 'Osteoarthritis', 'Hypothyroidism'], [
    e('Brufen 400', 'IBU', 0.98), f('aquazid 12.5', 'HCT', 0.9), e('Telma 40', 'TEL', 0.99),
    e('Thyronorm 50', 'LTX', 0.99), e('Shelcal 500', 'CAL', 0.97), e('Dolo 650', 'PCM', 0.97),
  ]),
  P('2283', 52, 'M', 82, 95, ['Hypertension', 'Gout'], [
    f('zylorik 100', 'ALL', 0.9), e('Losar 50', 'LOS', 0.98), f('T. Amlodipine 5mg', 'AML', 0.97),
    e('Montair 10', 'MNT', 0.98),
  ]),
  P('2284', 58, 'F', 61, 92, ['Hypothyroidism', 'Hypertension', 'Dyslipidaemia'], [
    e('Thyronorm 50mcg', 'LTX', 0.99), e('Amlong 5', 'AML', 0.98), e('Telma 40', 'TEL', 0.99),
    e('Atorva 10', 'ATV', 0.98), e('Shelcal 500', 'CAL', 0.97), f('calpol', 'PCM', 0.89),
  ]),
  P('2285', 66, 'M', 70, 49, ['Atrial fibrillation', 'Hypertension', 'Community-acquired pneumonia'], [
    f('Warf 5', 'WAR', 0.91), e('Claribid 500', 'CLR', 0.98), e('Amlopres 5', 'AML', 0.95),
    e('Storvas 20', 'ATV', 0.97), f('metolar25', 'MTP', 0.93),
  ]),
];
