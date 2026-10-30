// Words and number formats for values the pipeline produced. Display only: nothing here
// decides a severity, a match or a count.

import type { IssueType, Method, PinSlot, Severity } from './contract';

export const SEVERITY_LABEL: Record<Severity, string> = {
  contraindicated: 'Contraindicated', major: 'Major', moderate: 'Moderate', minor: 'Minor',
};

/** Status colour token per severity. Serious levels share the danger colour; minor is grey. */
export const SEVERITY_TONE: Record<Severity, string> = {
  contraindicated: 'var(--critical)', major: 'var(--critical)', moderate: 'var(--warn)', minor: 'var(--ink-3)',
};

export const ISSUE_LABEL: Record<IssueType, string> = {
  interaction: 'Drug interaction',
  duplicate_therapy: 'Duplicate therapy',
  renal_dose: 'Renal dose',
  contraindication: 'Contraindication',
};

/** How a line was resolved, in the words the medication panel uses. */
export const METHOD_LABEL: Record<Method, string> = {
  exact: 'exact name',
  synonym: 'known abbreviation',
  parts: 'written as parts',
  prefix: 'truncated name',
  fuzzy: 'approximate match',
  non_drug: 'not a medicine',
  abstained: 'verify manually',
};

export const METHOD_TAG: Record<Method, string> = {
  exact: 'tag-ok', synonym: 'tag-ok', parts: 'tag-action', prefix: 'tag-action', fuzzy: 'tag-action',
  non_drug: 'tag-grey', abstained: 'tag-warn',
};

export const PIN_LABEL: Record<PinSlot, string> = {
  collapse_hero: 'Interaction cluster',
  egfr_pair: 'Same drug, two kidneys',
  combination_duplicate: 'Hidden in a combination',
  abstention: 'Could not resolve',
  no_issue: 'Nothing labelled',
};

export const conf = (n: number) => n.toFixed(2);
export const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
export const num = (n: number, digits = 2) => n.toFixed(digits);
export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

const WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve'];
/** A count as a capitalised word for headlines ("Seven warnings"); digits past twelve. */
export const countWord = (n: number) => WORDS[n] ?? String(n);
