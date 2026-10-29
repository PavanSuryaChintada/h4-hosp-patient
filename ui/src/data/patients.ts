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
const a = (raw: string, candidates: [string, number][]): MedEntry => ({ raw, code: null, confidence: candidates[0][1], method: 'abstained', candidates });

const P = (id: string, age: number, sex: 'F' | 'M', weight: number, egfr: number, dx: string[], meds: MedEntry[], pregnant = false): Patient =>
  ({ id, age, sex, weight, egfr, pregnant, dx, meds });

export const HERO_ID = '2291';
export const CLEARED_ID = '2284';
export const CONTROL_ID = '2280';

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
  P('2286', 73, 'F', 57, 36, ['Type 2 diabetes', 'Diabetic neuropathy', 'Hypertension', 'Insomnia'], [
    e('Pregabid 75', 'PRE', 0.97), f('clonotrl 0.5', 'CLZ', 0.88), e('Glycomet 500', 'MTF', 0.99),
    e('Galvus 50', 'VIL', 0.97), e('Cardace 2.5', 'RAM', 0.96), e('Amaryl 1', 'GLM', 0.98),
  ]),
  P('2287', 39, 'F', 66, 112, ['Generalised anxiety', 'Tension headache'], [
    e('Serta 50', 'SER', 0.98), e('Restyl 0.25', 'ALP', 0.97), f('disprin', 'ASA', 0.9), e('Crocin 650', 'PCM', 0.98),
  ]),
  P('2288', 79, 'M', 63, 24, ['CKD stage 4', 'Post-herpetic neuralgia', 'Hypertension', 'Gout'], [
    e('Gabapin 300', 'GAB', 0.97), e('Amlong 10', 'AML', 0.98), e('Zyloric 300', 'ALL', 0.98),
    f('lasix40', 'FUR', 0.95), e('Shelcal 500', 'CAL', 0.97),
  ]),
  P('2289', 64, 'M', 76, 71, ['Coronary artery disease', 'Hypertension', 'Dyslipidaemia'], [
    e('Ecosprin 75', 'ASA', 0.98), f('Met-XL 25', 'MTF', 0.79, 'MTP'), e('Ramistar 5', 'RAM', 0.97),
    f('rosuvas 20mg', 'ROS', 0.95), e('Pantop 40', 'PAN', 0.98),
  ]),
  P('2290', 71, 'F', 54, 55, ['Major depression', 'Hypertension', 'GERD', 'Nausea'], [
    e('Nexito 20', 'ESC', 0.98), f('domstl 10', 'DOM', 0.89), e('Emeset 4', 'ODN', 0.97),
    e('Telma 40', 'TEL', 0.99), f('rablet20', 'RAB', 0.93),
  ]),
  P('2291', 74, 'F', 62, 28, ['Type 2 diabetes', 'Atrial fibrillation', 'Heart failure', 'Osteoarthritis'], [
    f('Warf 5', 'WAR', 0.91), e('Dynapar 50', 'DCF', 0.97), e('Envas 5mg', 'ENA', 0.96),
    e('Aldactone 25', 'SPI', 0.98), e('Lasix 40', 'FUR', 0.99), e('T. Metformin 500mg', 'MTF', 0.99),
    f('crocine', 'PCM', 0.88), e('Dolo 650', 'PCM', 0.97),
    a('PAN-D', [['pantoprazole', 0.52], ['pantoprazole + domperidone', 0.49]]),
  ]),
  P('2292', 47, 'M', 80, 101, ['Type 2 diabetes', 'Dyslipidaemia'], [
    e('Glyciphage 850', 'MTF', 0.97), e('Istavel 100', 'SIT', 0.98), e('Rosuvas 10', 'ROS', 0.98), f('telma 20mg', 'TEL', 0.96),
  ]),
  P('2293', 85, 'F', 44, 33, ['Dementia', 'Insomnia', 'Osteoporosis', 'Hypertension'], [
    f('stilnoc 10', 'ZOL', 0.87), e('Rivotril 0.5', 'CLZ', 0.97), f('tryptomer10', 'AMT', 0.94),
    e('Shelcal 500', 'CAL', 0.97), e('Amlong 2.5', 'AML', 0.98), e('Calpol 500', 'PCM', 0.97),
  ]),
  P('2294', 58, 'M', 85, 66, ['Hypertension', 'Asthma', 'Allergic rhinitis'], [
    e('Asthalin inhaler', 'SAL', 0.98), e('Montair 10', 'MNT', 0.98), f('okacet10', 'CET', 0.94),
    e('Concor 5', 'BIS', 0.97), e('Amlong 5', 'AML', 0.98),
  ]),
  P('2295', 74, 'M', 69, 39, ['Bipolar disorder', 'Hypertension', 'Osteoarthritis'], [
    e('Licab 300', 'LIT', 0.98), f('aquazide 25mg', 'HCT', 0.95), e('Envas 5', 'ENA', 0.96),
    f('voveran50', 'DCF', 0.93), e('Pantocid 40', 'PAN', 0.98),
  ]),
  P('2296', 68, 'M', 71, 57, ['Gout flare', 'Hypertension', 'Chest infection'], [
    e('Claribid 250', 'CLR', 0.97), a('Colcy 0.5', [['colchicine', 0.54], ['Colospa (mebeverine)', 0.5]]),
    e('Amlong 5', 'AML', 0.98), e('Zyloric 100', 'ALL', 0.98), e('Losar 50', 'LOS', 0.98),
  ]),
  P('2297', 60, 'F', 63, 76, ['Type 2 diabetes', 'Hypertension', 'Urinary tract infection'], [
    e('Daonil 5', 'GLB', 0.97), f('glycomet500', 'MTF', 0.96), f('levoflox500mg', 'LEV', 0.95), e('Envas 5', 'ENA', 0.96),
  ]),
  P('2298', 77, 'M', 59, 29, ['Heart failure', 'Atrial fibrillation', 'CKD stage 4'], [
    e('Lanoxin 0.125', 'DIG', 0.98), e('Lasix 80', 'FUR', 0.99), f('aldactone25', 'SPI', 0.95),
    e('Ramistar 2.5', 'RAM', 0.97), e('Concor 2.5', 'BIS', 0.97), e('Uniwarfin 3', 'WAR', 0.97),
  ]),
  P('2299', 29, 'F', 64, 118, ['Pregnancy, 24 weeks', 'Chronic hypertension', 'Anaemia'], [
    e('Telma 40', 'TEL', 0.99), e('Folvite 5', 'FOL', 0.98), e('Livogen', 'FER', 0.95),
    e('Emeset 4', 'ODN', 0.97), e('Calpol 500', 'PCM', 0.97),
  ], true),
  P('2300', 50, 'M', 90, 84, ['Epilepsy', 'Hypertension'], [
    e('Eptoin 100', 'PHE', 0.98), f('valparin200', 'VAL', 0.94), e('Amlong 5', 'AML', 0.98), e('Pantop 40', 'PAN', 0.98),
  ]),
  P('2301', 69, 'F', 60, 61, ['Type 2 diabetes', 'Hypertension', 'Hypothyroidism', 'Dyslipidaemia'], [
    e('Glycomet 1000', 'MTF', 0.97), e('Amaryl 2', 'GLM', 0.98), e('Istavel 50', 'SIT', 0.98),
    e('Telma 40', 'TEL', 0.99), f('aquazide12.5', 'HCT', 0.93), e('Thyronorm 75', 'LTX', 0.99),
    f('atorva20', 'ATV', 0.95), e('Omez 20', 'OME', 0.97),
  ]),
  P('2302', 57, 'M', 73, 69, ['GERD', 'Hypertension', 'Dyspepsia'], [
    a('Rabi-DSR', [['rabeprazole', 0.53], ['rabeprazole + domperidone', 0.51]]),
    e('Stamlo 5', 'AML', 0.97), f('losar 25mg', 'LOS', 0.96), e('Ecosprin 75', 'ASA', 0.98), e('Atorva 10', 'ATV', 0.98),
  ]),
  P('2303', 80, 'F', 50, 42, ['Osteoarthritis', 'Hypertension', 'Depression'], [
    f('hifenac', 'ACE', 0.91), e('Serta 50', 'SER', 0.98), e('Ecosprin 75', 'ASA', 0.98),
    e('Losar 50', 'LOS', 0.98), e('Calpol 650', 'PCM', 0.97),
  ]),
  P('2304', 44, 'F', 59, 99, ['Hypothyroidism', 'Iron deficiency anaemia'], [
    e('Eltroxin 100', 'LTX', 0.98), e('Livogen', 'FER', 0.95), e('Pantop 40', 'PAN', 0.98), f('crocin650', 'PCM', 0.95),
  ]),
  P('2305', 75, 'M', 67, 46, ['Atrial fibrillation', 'Type 2 diabetes', 'Tinea corporis'], [
    f('Warf 5', 'WAR', 0.91), e('Forcan 150', 'FLU', 0.97), e('Amaryl 2', 'GLM', 0.98),
    e('Glycomet 500', 'MTF', 0.99), e('Metolar 25', 'MTP', 0.97), f('storvas10', 'ATV', 0.94),
  ]),
  P('2306', 62, 'F', 68, 73, ['Hypertension', 'Dyslipidaemia', 'Allergic rhinitis'], [
    e('Amlong 5', 'AML', 0.98), f('simvotin 20', 'SIM', 0.92), e('Okacet', 'CET', 0.97), e('Telma 40', 'TEL', 0.99),
  ]),
  P('2307', 76, 'M', 64, 51, ['Heart failure', 'Atrial fibrillation', 'Hypertension'], [
    e('Lanoxin 0.25', 'DIG', 0.98), f('Lasx 40', 'LOS', 0.81, 'FUR'), e('Concor 2.5', 'BIS', 0.97),
    e('Envas 2.5', 'ENA', 0.96), e('Ecosprin 75', 'ASA', 0.98),
  ]),
  P('2308', 36, 'M', 75, 108, ['Peptic ulcer', 'H. pylori infection'], [
    e('Pantop 40', 'PAN', 0.98), e('Augmentin 625', 'AMC', 0.97), e('Claribid 500', 'CLR', 0.98), f('metrogyl400', 'MTZ', 0.94),
  ]),
  P('2309', 71, 'M', 70, 63, ['Type 2 diabetes', 'Coronary artery disease', 'Hypertension', 'Insomnia'], [
    f('glycomate 500', 'MTF', 0.88), e('Januvia 50', 'SIT', 0.98), e('Ecosprin 75', 'ASA', 0.98),
    e('Clopilet 75', 'CLO', 0.98), e('Pantop 40', 'PAN', 0.98), e('Metolar 50', 'MTP', 0.97),
    e('Ramistar 5', 'RAM', 0.97), e('Alprax 0.5', 'ALP', 0.98), e('Rosuvas 20', 'ROS', 0.98),
  ]),
];
