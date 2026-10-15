// Deterministic rule pass over the hardcoded cohort. Runs once at import time;
// the output is the same on every load, so every screen agrees with every other.

import { CLASS_LABEL, DRUG, DUPLICATE_CLASSES, findInteraction, type Modifier, type TableSeverity } from './drugs';
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
const lowerFirst = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

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

  // Renal dose vs eGFR
  const renal: Alert[] = [];
  for (const code of generics) {
    const r = DRUG[code].renal;
    if (!r) continue;
    let severity: Severity = 'low';
    let action = `No adjustment at eGFR ${p.egfr}; recheck yearly`;
    if (r.stop !== undefined && p.egfr < r.stop) { severity = 'high'; action = r.stopText!; }
    else if (p.egfr < r.reduce) { severity = p.egfr < 30 ? 'high' : 'medium'; action = r.reduceText; }
    renal.push({
      key: `renal:${code}`, kind: 'renal', type: 'Renal dose', drugs: [code],
      action: action.replace('{e}', String(p.egfr)), source: `Renal rule ${code}-R`,
      tableSeverity: 'renal flag', severity, rescored: `eGFR ${p.egfr}`, confidence: conf[code],
    });
  }

  // Duplicate therapy: the same generic twice, or two of one class
  const dupes: Alert[] = [];
  for (const code of generics) {
    const entries = resolved.filter((m) => m.code === code);
    if (entries.length < 2) continue;
    dupes.push({
      key: `dup:${code}`, kind: 'duplicate', type: 'Duplicate therapy', drugs: [code, code],
      action: `Keep one ${name(code)} product: "${entries[0].raw}" and "${entries[1].raw}" are the same drug`,
      source: 'Duplicate rule: same generic', tableSeverity: 'duplicate', severity: 'medium',
      confidence: Math.min(...entries.map((m) => m.confidence)),
    });
  }
  for (const cls of DUPLICATE_CLASSES) {
    const same = generics.filter((c) => DRUG[c].cls === cls);
    if (same.length < 2) continue;
    dupes.push({
      key: `dupcls:${cls}`, kind: 'duplicate', type: 'Duplicate therapy', drugs: same,
      action: `Keep one ${CLASS_LABEL[cls]}: ${same.map(name).join(' and ')}`,
      source: `Duplicate rule: same class (${CLASS_LABEL[cls]})`, tableSeverity: 'duplicate', severity: 'medium',
      confidence: Math.min(...same.map((c) => conf[c])),
    });
  }

  // Pregnancy
  const preg: Alert[] = [];
  if (p.pregnant) {
    for (const code of generics) {
      const rule = DRUG[code].preg;
      if (!rule) continue;
      preg.push({
        key: `preg:${code}`, kind: 'pregnancy', type: 'Pregnancy', drugs: [code], action: rule.text,
        source: `Pregnancy rule ${code}-P`, tableSeverity: rule.level === 'avoid' ? 'contraindicated' : 'caution',
        severity: rule.level === 'avoid' ? 'high' : 'medium', confidence: conf[code],
      });
    }
  }

  const all = [...interactions, ...renal, ...dupes, ...preg].sort(byPriority);

  // Collapse: the drug whose removal clears the most serious edges. Only drugs the rule
  // table marks as stoppable can anchor a cluster — warfarin or lithium never will.
  const serious = interactions.filter((x) => x.severity === 'high');
  const folded = new Set<string>();
  const clusters: Alert[] = [];
  const anchors: string[] = [];
  let open = serious.slice();
  let clearedByAnchor = 0;
  for (let round = 0; round < 2; round++) {
    const deg: Record<string, number> = {};
    for (const x of open) for (const d of x.drugs) deg[d] = (deg[d] ?? 0) + 1;
    const anchor = generics
      .filter((c) => DRUG[c].stop && (deg[c] ?? 0) >= 2)
      .sort((x, y) => deg[y] - deg[x] || (DRUG[y].stopRank ?? 0) - (DRUG[x].stopRank ?? 0))[0];
    if (!anchor) break;

    const cleared = open.filter((x) => x.drugs.includes(anchor));
    const partners = cleared.map((x) => x.drugs.find((d) => d !== anchor)!);
    const remainingInside = open.filter((x) => !x.drugs.includes(anchor) && x.drugs.every((d) => partners.includes(d)));
    const notes: string[] = [];

    for (const x of interactions) if (x.drugs.includes(anchor) && x.severity !== 'low') folded.add(x.key);
    const mediums = interactions.filter((x) => x.drugs.includes(anchor) && x.severity === 'medium');
    if (mediums.length) notes.push(`Also clears ${mediums.map((x) => `${name(anchor)} + ${name(x.drugs.find((d) => d !== anchor)!)}`).join(', ')} (medium).`);
    const anchorRenal = renal.find((x) => x.drugs[0] === anchor && x.severity !== 'low');
    if (anchorRenal) { folded.add(anchorRenal.key); notes.push(`Also flagged by the renal rule at eGFR ${p.egfr}.`); }
    if (remainingInside.length === 1) {
      const r = remainingInside[0];
      folded.add(r.key);
      notes.push(`Remaining: ${name(r.drugs[0])} + ${name(r.drugs[1])}, ${lowerFirst(r.action)}.`);
    }

    const involved = [anchor, ...partners];
    clusters.push({
      key: `cluster:${anchor}`, kind: 'cluster', type: 'Interaction cluster', drugs: involved,
      action: `${DRUG[anchor].stop} — clears ${cleared.length} of the ${serious.length} serious interactions`,
      note: notes.join(' '), source: `Graph collapse over ${cleared.map((x) => x.source.replace('Matched ', '')).join(', ')}`,
      tableSeverity: cleared.some((x) => x.tableSeverity === 'major') ? 'major' : 'moderate', severity: 'high',
      confidence: Math.min(...involved.map((c) => conf[c])),
    });
    anchors.push(anchor);
    if (round === 0) clearedByAnchor = cleared.length;
    open = open.filter((x) => !x.drugs.includes(anchor) && !folded.has(x.key));
  }

  const collapsed = [
    ...clusters,
    ...all.filter((x) => x.severity !== 'low' && !folded.has(x.key)),
  ].sort(byPriority);

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
