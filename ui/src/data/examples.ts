// Ready-made entries for a live demo, so nobody types during a presentation. Each stands in for
// what a nurse, lab technician, pharmacist or prescriber would type, and goes through the same
// server and the same pipeline as anything typed by hand. None of it is pipeline output: what
// the check finds on these patients is whatever the pipeline finds.

export type DemoPatient = { label: string; story: string; fields: Record<string, string>; medication_list: string };

/** Two patients written so every role has something to do: an unreadable line, eGFR-dependent drugs, serious pairs. */
export const DEMO_PATIENTS: DemoPatient[] = [
  {
    label: 'Demo patient 1: kidneys and a messy list',
    story: '74, female, diabetic on warfarin. One line the system cannot read, two kidney-dependent drugs, paracetamol written twice.',
    fields: { age: '74', sex: 'F', weight_kg: '58', pregnant: 'N', diagnoses: 'T2DM; HTN; AF on anticoagulation; knee OA', allergies: 'NKDA', prescriber_count: '3' },
    medication_list: [
      'Tab Glycomet 500 BD', 'Tab Warf 5mg OD', 'Brufen 400 tds for knee pain', 'T. Telma 40 OD',
      'Tab. Ditr 10 0-0-1', 'Dolo 650 SOS', 'Crocin 500 sos', 'Pan 40 OD before breakfast',
    ].join('\n'),
  },
  {
    label: 'Demo patient 2: a contraindicated combination',
    story: '66, male, angina and erectile dysfunction. Two nitrates with two PDE5 inhibitors from different prescribers: the hard stop.',
    fields: { age: '66', sex: 'M', weight_kg: '74', pregnant: 'NA', diagnoses: 'chronic stable angina; erectile dysfunction; gout; COPD', allergies: 'NKDA', prescriber_count: '2' },
    medication_list: [
      'T. nikoran 5 1-0-1 after food', 'Tab Angised 0.5mg SOS for chest pain', 'Sildenafil 50 sos', 'Megal 10 SOS',
      'Tab Ecosprin 150 OD', 'T. rosuvas 10 hs', 'Tab theophylline 400 BD', 'Tab Zyloric 100 OD',
    ].join('\n'),
  },
];

/** eGFR the lab technician can enter: one where the kidney rules bite, one where they do not. */
export const EGFR_EXAMPLES = [
  { value: '28', label: 'eGFR 28', hint: 'severely decreased: the kidney-dose rules fire' },
  { value: '80', label: 'eGFR 80', hint: 'near normal: the kidney alerts clear' },
];

/** Lines a nurse adds when the patient remembers one more medicine. */
export const ADD_LINE_EXAMPLES = ['Tab Pan 40 OD before breakfast', 'Shelcal 500 BD'];

/** Override reasons (from medsafe.workflow.OVERRIDE_REASONS) with a note a prescriber might write. */
export const OVERRIDE_EXAMPLES = [
  { reason: 'intended therapy', note: 'Reviewed with cardiology today; monitoring daily' },
  { reason: 'benefit outweighs risk', note: 'Short course only, stopping in 3 days' },
];

/** Notes for a pharmacist-review handoff. */
export const REVIEW_NOTES = [
  'Please reconcile the doses against today\'s eGFR',
  'Patient brought strips from two prescribers; please check for duplicates',
];
