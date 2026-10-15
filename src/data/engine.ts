// Deterministic rule pass over the hardcoded cohort. Runs once at import time;
// the output is the same on every load, so every screen agrees with every other.

import { DRUG, findInteraction, type Modifier, type TableSeverity } from './drugs';
import { PATIENTS, type Patient } from './patients';

export type Severity = 'high' | 'medium' | 'low';
export type Kind = 'cluster' | 'interaction' | 'renal' | 'duplicate' | 'pregnancy';

export type Alert = {
  key: string;
  kind: Kind;
  type: string;
  drugs: string[];
  action: string;
  note?: string;
  source: string;
  tableSeverity: string;
  severity: Severity;
  rescored?: string;
  confidence: number;
};

export type Edge = { a: string; b: string; severity: Severity; rule: string };

export type Analysis = {
  patient: Patient;
  generics: string[];
  checked: number;
  unresolved: number;
  all: Alert[];
  collapsed: Alert[];
  edges: Edge[];
  anchors: string[];
  serious: number;
  clearedByAnchor: number;
  top: Severity | 'cleared';
  summary: string;
};

export const name = (code: string) => DRUG[code].name;

const SEV_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };
const KIND_RANK: Record<Kind, number> = { cluster: 0, pregnancy: 1, interaction: 2, renal: 3, duplicate: 4 };
const byPriority = (x: Alert, y: Alert) =>
  SEV_RANK[x.severity] - SEV_RANK[y.severity] || KIND_RANK[x.kind] - KIND_RANK[y.kind] || y.confidence - x.confidence;

const fill = (tpl: string, a: string, b: string) => tpl.replace('{a}', name(a)).replace('{b}', name(b));

function rescore(sev: TableSeverity, mod: Modifier, p: Patient): [Severity, string?] {
  if (sev === 'minor') return ['low'];
  if (sev === 'major') {
    if (mod === 'renal' && p.egfr >= 90 && p.age < 60) return ['medium', `eGFR ${p.egfr}`];
    return ['high'];
  }
  if (mod === 'renal' && p.egfr < 45) return ['high', `eGFR ${p.egfr}`];
  if (mod === 'bleed' && p.age >= 75) return ['high', `age ${p.age}`];
  if (mod === 'bleed' && p.weight < 50) return ['high', `weight ${p.weight} kg`];
  if (mod === 'cns' && p.age >= 65) return ['high', `age ${p.age}`];
  if (mod === 'elderly' && p.age >= 75) return ['high', `age ${p.age}`];
  return ['medium'];
}

export function analyse(p: Patient): Analysis {
  const resolved = p.meds.filter((m) => m.code);
  const generics = [...new Set(resolved.map((m) => m.code!))];
  const conf: Record<string, number> = {};
  for (const m of resolved) conf[m.code!] = Math.max(conf[m.code!] ?? 0, m.confidence);

  // Interactions, every pair
  const interactions: Alert[] = [];
  const edges: Edge[] = [];
  for (let i = 0; i < generics.length; i++) {
    for (let j = i + 1; j < generics.length; j++) {
      const hit = findInteraction(generics[i], generics[j]);
      if (!hit) continue;
      const { rule, a, b } = hit;
      const [severity, rescored] = rescore(rule.severity, rule.mod, p);
      interactions.push({
        key: `${rule.id}:${a}-${b}`, kind: 'interaction', type: 'Interaction', drugs: [a, b],
        action: fill(rule.action, a, b), note: rule.mechanism, source: `Matched ${rule.id}`,
        tableSeverity: rule.severity, severity, rescored, confidence: Math.min(conf[a], conf[b]),
      });
      edges.push({ a, b, severity, rule: rule.id });
    }
  }

  const all = interactions.slice().sort(byPriority);

  const serious = interactions.filter((x) => x.severity === 'high');
  const anchors: string[] = [];
  const clearedByAnchor = 0;
  const collapsed = all.filter((x) => x.severity !== 'low');

  const unresolved = p.meds.length - resolved.length;
  const top = collapsed[0]?.severity ?? 'cleared';
  const summary = collapsed.length
    ? collapsed[0].action
    : unresolved
      ? `No issue found in ${resolved.length} of ${p.meds.length} medicines. ${unresolved} name unresolved, verify manually`
      : `No issue found in ${p.meds.length} medicines`;

  return {
    patient: p, generics, checked: resolved.length, unresolved, all, collapsed, edges, anchors,
    serious: serious.length, clearedByAnchor, top, summary,
  };
}

export const ANALYSES: Analysis[] = PATIENTS.map(analyse);
export const BY_ID: Record<string, Analysis> = Object.fromEntries(ANALYSES.map((x) => [x.patient.id, x]));
