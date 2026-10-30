import type { Medication } from '../data/contract';
import { METHOD_LABEL, METHOD_TAG, conf } from '../data/format';

/** The resolver's output for one line, as tags: how it matched, and whether a combination opened. */
export function MedTags({ m }: { m: Medication }) {
  if (m.confirmed) {
    return <span className="med-tags"><span className="tag tag-ok" title={`${m.confirmed.by}, ${m.confirmed.at}`}>confirmed by {m.confirmed.role}</span></span>;
  }
  return (
    <span className="med-tags">
      {m.status === 'stopped' && <span className="tag tag-grey">marked stopped, not checked</span>}
      {m.combination === 'brand' && <span className="tag tag-action">combination expanded</span>}
      {(m.method !== 'exact' || m.combination !== 'brand') && <span className={`tag ${METHOD_TAG[m.method]}`}>{METHOD_LABEL[m.method]}</span>}
    </span>
  );
}

/** One written line: the raw string in mono grey, an arrow, what it resolved to, the confidence, the tag. */
export function MedRow({ m, highlight = false }: { m: Medication; highlight?: boolean }) {
  const abstained = m.method === 'abstained';
  const nonDrug = m.method === 'non_drug';
  return (
    <div className={`medrow${abstained ? ' abst' : ''}${highlight ? ' hl' : ''}`}>
      <span className="raw" title={m.raw}>"{m.raw}"</span>
      <span className="arr" aria-hidden="true">→</span>
      {abstained ? (
        <span className="res">
          could not resolve
          {m.candidates.length > 0 && (
            <span className="cand">closest: {m.candidates.map(([g, s]) => `${g} ${conf(s)}`).join(' · ')}</span>
          )}
        </span>
      ) : nonDrug ? (
        <span className="res res-none">not a medicine</span>
      ) : (
        <span className="res">{m.generics.join(' ; ')}</span>
      )}
      <span className="cf mono">{conf(m.confidence)}</span>
      <MedTags m={m} />
    </div>
  );
}

export function MedicationPanel({ meds, highlight = [] }: { meds: Medication[]; highlight?: number[] }) {
  return (
    <div className="medlist">
      <div className="medrow medhead" aria-hidden="true">
        <span>As written</span><span /><span>Resolved to</span><span className="cf">Confidence</span><span>How</span>
      </div>
      {meds.map((m) => <MedRow key={m.index} m={m} highlight={highlight.includes(m.index)} />)}
    </div>
  );
}
