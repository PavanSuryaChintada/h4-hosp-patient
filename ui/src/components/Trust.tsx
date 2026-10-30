// The trust panel: what this check saw, what it could not check, who decides, and the handoff
// to a pharmacist. Persistent on the patient screen, never a dismissible footer. The summary,
// the not-checked list and the disclaimer are the pipeline's text (medsafe.explain.limitations).

import { useState } from 'react';
import { useAuth } from '../auth';
import type { PatientView, WardRecord } from '../data/contract';
import { useHandoffs } from '../data/handoff';
import { useData } from '../data/load';
import { REVIEW_NOTES } from '../data/examples';
import { QuickFill } from './QuickFill';
import { Icon } from './viz';

export type WardTrust = {
  requested: boolean;
  history: WardRecord['history'];
  onRequest: (note: string) => Promise<boolean>;
};

function when(iso: string) {
  return new Date(iso).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short', year: 'numeric' });
}

function Escalate({ onSubmit, label }: { onSubmit: (note: string) => Promise<boolean> | void; label: string }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  if (!open) {
    return <button type="button" className="btn btn-secondary btn-block" onClick={() => setOpen(true)}><Icon name="flag" size={16} />{label}</button>;
  }
  return (
    <div className="handoff-form">
      <label className="field" style={{ marginTop: 0 }}>
        <span className="label">Note for the pharmacist (optional)</span>
        <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <QuickFill picks={REVIEW_NOTES.map((n) => ({ label: n, onPick: () => setNote(n) }))} />
      <div className="handoff-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={async () => { await onSubmit(note); setNote(''); setOpen(false); }}>Record handoff</button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  );
}

/** Demo patients from the export: handoffs are kept in this browser. */
function LocalHandoff({ id }: { id: string }) {
  const { user } = useAuth();
  const { handoffs, record } = useHandoffs(id);
  return (
    <>
      <Escalate label="Flag for pharmacist review" onSubmit={(note) => record({ by: user?.name ?? 'Signed-in user', role: user?.role ?? '', note: note.trim() })} />
      {handoffs.length > 0 && (
        <ol className="handoffs" aria-label="Handoffs recorded">
          {handoffs.map((h) => (
            <li key={h.at}>
              <span className="handoff-what">Flagged for pharmacist review</span>
              <span className="meta"><span className="mono">{when(h.at)}</span> · {h.by}{h.role ? `, ${h.role}` : ''}</span>
              {h.note && <span className="handoff-note">{h.note}</span>}
            </li>
          ))}
        </ol>
      )}
      <p className="trust-meta">Training-set patients keep handoffs in this browser. Ward patients record them on the ward server.</p>
    </>
  );
}

/** Ward patients: the request is recorded on the server; a pharmacist closes it. */
function WardHandoff({ ward }: { ward: WardTrust }) {
  const { user } = useAuth();
  const reviews = ward.history.filter((h) => h.entry === 'review_requested' || h.entry === 'review_closed');
  return (
    <>
      {user?.key === 'reviewer' ? null : ward.requested
        ? (user?.key === 'pharmacist'
          ? <Escalate label="Close the review" onSubmit={ward.onRequest} />
          : <p className="trust-meta">Pharmacist review requested and open.</p>)
        : <Escalate label="Flag for pharmacist review" onSubmit={ward.onRequest} />}
      {reviews.length > 0 && (
        <ol className="handoffs" aria-label="Review requests">
          {reviews.map((h) => (
            <li key={h.at + h.entry}>
              <span className="handoff-what">{h.entry === 'review_closed' ? 'Review closed' : 'Pharmacist review requested'}</span>
              <span className="meta"><span className="mono">{when(h.at)}</span> · {h.user}, {h.role}</span>
              {h.detail && <span className="handoff-note">{h.detail}</span>}
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

export function TrustPanel({ p, ward }: { p: PatientView; ward?: WardTrust }) {
  const { x } = useData();
  const m = p.compare.medsafe;
  const statement = p.medsafe.summary
    ?? 'The rule checks have not run on this list: the rule engine is not built. Only the names have been read.';

  return (
    <aside className="trust" aria-label="What this check saw">
      <h2 className="section">What this check saw</h2>
      <p className="trust-statement">{statement}</p>

      <dl className="trust-cover">
        <div><dt>Lines on the list</dt><dd className="mono">{m.lines}</dd></div>
        <div><dt>Resolved to a medicine</dt><dd className="mono">{m.checked}</dd></div>
        <div><dt>To verify manually</dt><dd className="mono" style={{ color: m.to_verify ? 'var(--warn)' : undefined }}>{m.to_verify}</dd></div>
        <div><dt>Dropped</dt><dd className="mono">{m.dropped}</dd></div>
      </dl>

      <h3 className="trust-h">Could not check</h3>
      <ul className="trust-list">
        {(p.medsafe.not_checked ?? ['Every rule check: not built yet.']).map((n) => <li key={n}>{n}</li>)}
        {p.notes.map((n) => <li key={n}>{n}</li>)}
        {p.medsafe.not_checked?.length === 0 && p.notes.length === 0 && <li>Nothing on this list was left unchecked.</li>}
      </ul>
      <p className="trust-meta">Every alert carries its confidence, the rule that fired and what could not be checked.</p>

      <p className="trust-decides"><Icon name="person" size={16} />{x.workflow.disclaimer}</p>

      <div className="trust-escalate">{ward ? <WardHandoff ward={ward} /> : <LocalHandoff id={p.id} />}</div>
    </aside>
  );
}
