// The UI data contract: what tools/export_ui.py writes to public/data/pipeline.json.
// Change both files together and bump SCHEMA_VERSION in each.
//
// The UI reads this file and nothing else. It holds no detection logic: every count, severity,
// tier, match and choice of demo patient below was computed in Python from pipeline output,
// from the standard-check reproduction (tools/ehr_reference.py), or from an evaluation report.
// A field that is null because its pipeline stage is not built must render as "not built",
// never as "nothing found".

export const SCHEMA_VERSION = 2;

export type Severity = 'contraindicated' | 'major' | 'moderate' | 'minor';
export type IssueType = 'interaction' | 'duplicate_therapy' | 'renal_dose' | 'contraindication';
export type Method = 'exact' | 'synonym' | 'parts' | 'prefix' | 'fuzzy' | 'non_drug' | 'abstained';

/** One written line, as the pipeline resolved it. `truth` is the training label (Resolution screen only). */
export type Medication = {
  index: number;
  raw: string;
  generics: string[];
  method: Method;
  confidence: number;
  abstain_reason: string | null;
  candidates: [string, number][];
  combination: 'brand' | 'written' | null;
  /** Whether the rules counted the line. */
  status: 'active' | 'stopped' | 'not_a_medicine' | 'unresolved' | null;
  truth: { match: boolean; kind: string | null; generics?: string[] } | null;
  /** Ward records only: a pharmacist named the generic(s) on a line the resolver would not guess. */
  confirmed?: { generics: string[]; by: string; role: string; at: string } | null;
};

/** A Medsafe finding, in medsafe.explain.prioritise order. Minor ones are shown, not submitted. */
export type MedsafeAlert = {
  rank: number;
  key: string;                // "issue_type:drug;drug", how the audit log names it
  issue_type: IssueType;
  severity: Severity;
  drugs: string[];
  suggested_action: string;
  confidence: number;
  rule_id: string;
  reasons: string[];          // the patient values and table rows behind it
  limitations: string;        // the confidence-and-limitations text the pack requires
  entries: number[];          // medication indices involved
  tier: { egfr_below: number; severity: Severity } | null;   // renal alerts: the tier applied
  submitted: boolean;         // in the predictions file (minor alerts are not)
};

/** What a prescriber is asked to do: the collapse first, then each other submitted alert. */
export type Action = { kind: 'collapse'; summary: string; drugs: string[]; covers: number[] } | { kind: 'alert'; rank: number };

/** medsafe.explain.prioritise.collapse, with every interaction for the graph. */
export type Collapse = {
  chosen: string[];
  summary: string | null;
  total: number;
  nodes: string[];
  edges: { a: string; b: string; severity: Severity; cleared: boolean }[];
};

export type MedsafeView = {
  alerts: MedsafeAlert[] | null;
  actions: Action[] | null;
  collapse: Collapse | null;
  suppressed: number | null;
  summary: string | null;           // medsafe.explain.limitations.patient_summary, word for word
  not_checked: string[] | null;     // medsafe.explain.limitations.not_checked
};

export type EhrAlert = {
  issue_type: IssueType;
  severity: Severity;
  drugs: string[];
  entries: number[];
  source: string;
  effect: string | null;
  action: string | null;
};

export type Compare = {
  ehr: {
    alerts: number;
    by_severity: Record<Severity, number>;
    not_in_formulary: number;
    combinations_unexpanded: number;
    egfr_read: false;
  };
  medsafe: {
    lines: number;
    medicines: number;
    checked: number;
    dropped: number;
    to_verify: number;
    combinations_expanded: number;
    actions: number | null;
    egfr: number | null;
    egfr_tier: { generic: string; egfr_below: number; severity: Severity } | null;
  };
};

export type PatientView = {
  id: string;
  age: number | null;
  sex: string | null;
  weight_kg: number | null;
  egfr: number | null;
  pregnant: boolean | null;
  diagnoses: string[];
  allergies: string | null;
  prescriber_count: number | null;
  unreadable_fields: string[];
  notes: string[];
  medications: Medication[];
  medsafe: MedsafeView;
  ehr: { matched: (string | null)[]; alerts: EhrAlert[] };
  compare: Compare;
};

/** A training label: the answer key. Shown as such, never as Medsafe's output. */
export type Label = { issue_type: IssueType; severity: Severity; drugs: string[]; near_miss: boolean };

export type PinSlot = 'collapse_hero' | 'egfr_pair' | 'combination_duplicate' | 'abstention' | 'no_issue';
export type Pin = { slot: PinSlot; patient_ids: string[]; basis: 'labels' | 'pipeline'; why: string | null };

/** `ehr_alert` / `medsafe_alert`: index into that patient's alerts raising the labelled issue. */
export type PairSide = { patient_id: string; line: number; egfr: number; ehr_alert: number | null; medsafe_alert: number | null };

export type Cards = {
  brand_chaos: {
    patient_id: string; generic: string; lines: number[]; label: Label;
    ehr_alert: number | null; medsafe_alert: number | null;
  } | null;
  hidden_generic: {
    patient_id: string; generic: string; combination_lines: number[]; other_lines: number[];
    label: Label; ehr_alert: number | null; medsafe_alert: number | null;
  } | null;
  egfr_pair: {
    generic: string; low: PairSide; high: PairSide;
    ladder: { egfr_below: number; severity: Severity; action: string | null }[];
    label: Label;
  } | null;
  alert_fatigue: {
    patient_id: string; ehr_alerts: number; serious_labelled: number; serious_raised: number; missed: Label[];
  } | null;
};

/** The organisers' evaluate.py report, unchanged. */
export type OfficialScore = {
  primary_score: number;
  components: {
    serious_recall: number;
    near_miss_serious_recall: number;
    precision_all: number;
    graded_recall_non_minor: number;
    resolution_accuracy: number;
    base_score: number;
    noise_alerts_per_patient: number;
    alert_fatigue_multiplier: number;
  };
  counts: {
    patients_scored: number;
    true_issues: number;
    true_serious: number;
    true_near_miss: number;
    alerts_scored: number;
    alerts_matched: number;
    false_alerts: number;
    alerts_on_minor_issues: number;
    tokens_scored: number;
  };
  per_issue_type: Record<IssueType, { serious_true: number; serious_recall: number; alerts: number; alerts_matched: number }>;
  resolution_accuracy_misspelled: number;
  resolution_accuracy_by_token_kind: Record<string, number>;
};

export type NearMiss = {
  patient_id: string; issue_type: IssueType; severity: Severity; drugs: string;
  as_written: string; drugs_resolved: boolean; status: string;
};

export type EvalSplit = {
  split: string;
  patients: number;
  stages_built: string[];
  official: OfficialScore;
  resolution: {
    lines: number; accuracy: number; misspelled_accuracy: number;
    false_resolutions: number; false_resolution_rate: number; abstentions: number; abstention_rate: number;
  };
  near_misses: NearMiss[];
  /** Reference submissions scored by the same scorer: oracle, flag nothing, the pack baseline. */
  baselines: Record<string, OfficialScore>;
};

export type Report = {
  generated_at: string;
  git_revision: string;
  data_version: string;
  splits: Record<string, EvalSplit>;
};

/** medsafe.workflow: who may do and enter what. The portal enforces none of it on its own. */
export type Role = 'prescriber' | 'pharmacist' | 'nurse' | 'lab';
export type AlertEvent = 'shown' | 'accept' | 'override' | 'defer' | 'escalate';
export type Entry = 'admit' | 'medication_list' | 'abha_pull' | 'egfr' | 'confirm_name';
export type Workflow = {
  roles: Role[];
  events: AlertEvent[];
  permissions: Record<Role, AlertEvent[]>;
  entries: Record<Role, Entry[]>;
  override_reasons: string[];
  disclaimer: string;
  generics: string[];
};

/** One line of the append-only audit log (medsafe.workflow.AuditEvent). */
export type AuditEvent = {
  timestamp: string; user: string; role: Role; patient_id: string; alert: string;
  event: AlertEvent; reason: string | null; note: string | null;
};

/** A hand-entered patient on the ward, from tools/serve_ui.py. `result` is checked by the real pipeline. */
export type WardRecord = {
  id: string;
  created_at: string;
  created_by: string;
  fields: Record<string, string>;
  egfr: string | null;
  lines: { raw: string; confirmed: Medication['confirmed'] }[];
  history: { at: string; user: string; role: string; entry: string; detail: string }[];
  review_requested: boolean;
  /** Set when the list started from records fetched through the ABHA sandbox. */
  source: { kind: 'abha_sandbox'; consent_id: string; address: string } | null;
  /** eGFR found in those records, for the lab technician to confirm; never applied on its own. */
  abha_egfr: string | null;
  result: PatientView;
  alert_states: Record<string, AuditEvent>;
  events: AuditEvent[];
  pharmacist_queue: string[];
};

export type WardRow = {
  id: string; created_at: string; created_by: string; age: number | null; sex: string | null;
  egfr: number | null; lines: number; actions: number | null; to_verify: number; pharmacist_queue: string[];
};

/** A consent in the ABHA sandbox (tools/serve_ui.py). Simulated; never connected to ABDM. */
export type Consent = {
  id: string; address: string; purpose: string; status: 'requested' | 'granted';
  requested_by: string; role: string; requested_at: string; expires_at: string;
  approved_at: string | null; approved_by?: string; fetched_at: string | null;
};
export type AbhaBundle = {
  consent: Consent; fields: Record<string, string>; medication_list: string;
  lab: { egfr: string | null }; source: string;
};

export type OverridePattern = { issue_type: IssueType; shown: number; overridden: number; rate: number; reasons: [string, number][] };

export type Export = {
  schema_version: number;
  source: { split: 'train' | 'test'; patients: number; generator: string; command: string };
  stages: { id: string; phase: string | null; built: boolean }[];
  settings: Record<string, number>;
  patients: PatientView[];
  workflow: Workflow;
  resolution: {
    lines: number; by_method: Partial<Record<Method, number>>; brand_combinations: number;
    patients_with_lines_to_verify: number; label_mismatches: number | null;
  };
  demo: { pins: Pin[]; cards: Cards } | null;
  ehr_reference: {
    cohort: {
      patients: number; alerts: number; alerts_per_patient: number;
      alerts_per_patient_by_severity: Record<Severity, number>; lines: number; lines_not_in_formulary: number;
    };
    score: { split: string; official?: OfficialScore; unavailable?: string } | null;
  };
  evaluation: { path: string | null; report?: Report; unavailable?: string };
  /** python -m eval.ml_challenger: a trained name-resolution model against the rules, on holdout. */
  ml_challenger: {
    path: string; generated_at: string;
    /** Stage 1: a learned drug-name matcher. */
    names: {
      thresholds: { min_similarity: number; min_margin: number; cv_accuracy: number; folds: number; lines: number };
      training_lines: number; holdout_patients: number;
      submissions: Record<string, Brief & {
        lines: { lines: number; accuracy: number; misspelled_accuracy: number; unseen_lines: number;
          unseen_accuracy: number; unseen_misspelled_accuracy: number; wrong_confident: number; abstained: number };
      }>;
    };
    /** Stage 2: a learned reader of conditions and negation in diagnosis text. */
    conditions: {
      examples: number; present: number; threshold: number; cv_f1: number; folds: number;
      pairs: Record<string, { pairs: number; present: number; precision: number; recall: number; f1: number }>;
      official: Record<string, Brief>;
    };
    /** Stage 3: boosted trees that hold back a standard check's low-value alerts. */
    triage: {
      training_alerts: number; worth_showing: number; threshold: number; holdout_alerts: number;
      holdout_auc: number; held_back: number; held_back_worth_showing: number; importance: [string, number][];
      official: Record<string, Brief>;
    };
  } | null;
};

/** One submission's official result, trimmed: score, components, contraindication figures. */
export type Brief = {
  primary_score: number;
  components: OfficialScore['components'];
  contraindication: { serious_true: number; serious_recall: number; alerts: number; alerts_matched: number };
};
