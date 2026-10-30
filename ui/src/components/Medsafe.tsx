// Medsafe's own output: prioritised actions, decisions on them, and the collapse graph. All of it
// renders pipeline output (medsafe.explain.prioritise, medsafe.explain.limitations) and the
// policy in medsafe.workflow; none of it is decided here.

import { useState } from 'react';
import { useAuth } from '../auth';
import type { AlertEvent, AuditEvent, Collapse, MedsafeAlert, PatientView } from '../data/contract';
import { ISSUE_LABEL, SEVERITY_TONE, conf, plural } from '../data/format';
import { useData } from '../data/load';
import { NotBuilt, StatusInline } from './ui';

export type Decisions = {
  states: Record<string, AuditEvent>;
  onEvent: (alert: string, event: AlertEvent, reason?: string, note?: string) => Promise<boolean>;
};

const DONE: Record<AlertEvent, string> = {
  shown: 'Shown', accept: 'Accepted', override: 'Overridden', defer: 'Deferred to pharmacist', escalate: 'Escalated to pharmacist',
};
const ASK: Record<Exclude<AlertEvent, 'shown'>, string> = {
  accept: 'Accept', override: 'Override', defer: 'Defer to pharmacist', escalate: 'Escalate to pharmacist',
};

function when(iso: string) {
  return new Date(iso).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' });
}

/** The latest decision on an alert, and the actions this role may take (medsafe.workflow.PERMISSIONS). */
function Decide({ alert, d }: { alert: MedsafeAlert; d: Decisions }) {
  const { x } = useData();
  const { user } = useAuth();
  const [overriding, setOverriding] = useState(false);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const state = d.states[alert.key];
  const allowed = user && user.key !== 'reviewer' ? x.workflow.permissions[user.key].filter((e) => e !== 'shown') : [];

  const act = async (event: AlertEvent) => {
    if (event === 'override') { setOverriding(true); return; }
    await d.onEvent(alert.key, event);
  };
  const override = async () => {
    if (await d.onEvent(alert.key, 'override', reason, note)) { setOverriding(false); setReason(''); setNote(''); }
  };

  return (
    <div className="decide">
      {state ? (
        <p className={`decide-state ev-${state.event}`}>
          {DONE[state.event]} by {state.user} <span className="ink-3">({state.role}, <span className="mono">{when(state.timestamp)}</span>)</span>
          {state.reason && <>: {state.reason}</>}{state.note && <span className="ink-2"> · {state.note}</span>}
        </p>
      ) : <p className="decide-state ink-3">No decision recorded.</p>}
      {allowed.length > 0 && !overriding && (
        <div className="decide-actions">
          {allowed.map((e) => (
            <button key={e} type="button" className={`btn btn-sm ${e === 'accept' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => act(e)}>{ASK[e as Exclude<AlertEvent, 'shown'>]}</button>
          ))}
        </div>
      )}
      {overriding && (
        <div className="decide-override">
          <label className="field" style={{ marginTop: 0 }}>
            <span className="label">Reason for overriding (required)</span>
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="">Choose a reason</option>
              {x.workflow.override_reasons.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="label">Note{reason === 'other' ? ' (required for "other")' : ''}</span>
            <input value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="decide-actions">
            <button type="button" className="btn btn-primary btn-sm" disabled={!reason} onClick={override}>Record override</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setOverriding(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export function MedsafeAlertCard({ a, d, compact = false }: { a: MedsafeAlert; d?: Decisions; compact?: boolean }) {
  return (
    <article className={`ms-alert${a.submitted ? '' : ' ms-minor'}`} style={{ ['--c' as string]: SEVERITY_TONE[a.severity] }}>
      <header className="ms-head">
        <span className="mono ms-rank">{a.rank}</span>
        <StatusInline severity={a.severity} />
        <span className="ms-type">{ISSUE_LABEL[a.issue_type]}</span>
        <span className="ms-conf">confidence <span className="mono">{conf(a.confidence)}</span></span>
      </header>
      <p className="ms-action">{a.suggested_action}</p>
      <p className="ms-drugs mono">{a.drugs.join(' + ')}</p>
      {a.tier && (
        <p className="ms-tier">Rule tier: eGFR &lt; <span className="mono">{a.tier.egfr_below}</span>, {a.tier.severity}, the most restrictive tier that applies.</p>
      )}
      {!compact && a.reasons.map((r) => <p key={r} className="ms-why">{r}</p>)}
      <p className="ms-limit">{a.limitations}</p>
      {d && <Decide alert={a} d={d} />}
    </article>
  );
}

/** The actions panel: the collapse first, then each other submitted alert, then minor ones last. */
export function Actions({ p, d }: { p: PatientView; d?: Decisions }) {
  const { actions, alerts, summary } = p.medsafe;
  if (actions === null || alerts === null) {
    return <NotBuilt stage="output" what="Prioritised actions come from the rule engine and the output policy." />;
  }
  const byRank = new Map(alerts.map((a) => [a.rank, a]));
  const minor = alerts.filter((a) => !a.submitted);
  return (
    <div className="ms-list">
      {actions.length === 0 && <p className="empty-ok">{summary}</p>}
      {actions.map((act) => act.kind === 'collapse' ? (
        <section key="collapse" className="ms-collapse" aria-label="Review first">
          <p className="ms-collapse-head">{act.summary}</p>
          <div className="ms-collapse-list">
            {act.covers.map((r) => <MedsafeAlertCard key={r} a={byRank.get(r)!} d={d} compact />)}
          </div>
        </section>
      ) : <MedsafeAlertCard key={act.rank} a={byRank.get(act.rank)!} d={d} />)}
      {minor.length > 0 && (
        <details className="ms-minors">
          <summary>{plural(minor.length, 'minor issue')}, shown last and not sent as alerts</summary>
          <p className="meta">Minor issues are real but low-value. Sent as alerts they add to the noise in which a serious one gets dismissed.</p>
          {minor.map((a) => <MedsafeAlertCard key={a.rank} a={a} d={d} compact />)}
        </details>
      )}
    </div>
  );
}

/**
 * Drugs as nodes, interactions as edges, on fixed positions around an ellipse: no force
 * simulation, so nodes never move between renders. The drugs to review first are filled.
 * `removed` draws the list once those drugs are reviewed: the edges they clear fade out.
 * `unchecked` adds the lines the resolver would not guess, as dashed "?" nodes.
 */
export function AlertGraph({ c, width = 440, height = 260, removed = false, unchecked = [] }: {
  c: Collapse; width?: number; height?: number; removed?: boolean; unchecked?: string[];
}) {
  const order = [...c.chosen, ...c.nodes.filter((n) => !c.chosen.includes(n))];
  const total = Math.max(order.length + unchecked.length, 1);
  const compact = width < 440;
  const cx = width / 2, cy = height / 2, rx = compact ? width / 2 - 80 : width / 2 - 96, ry = height / 2 - 40;
  const pos = (i: number) => {
    const t = -Math.PI / 2 + (i / total) * Math.PI * 2;
    return { x: cx + rx * Math.cos(t), y: cy + ry * Math.sin(t), cos: Math.cos(t), sin: Math.sin(t) };
  };
  const at = new Map(order.map((n, i) => [n, pos(i)]));
  const serious = (s: string) => s === 'contraindicated' || s === 'major';
  const aria = c.summary ?? `Alert graph: ${order.length} drugs, ${c.edges.length} interactions; no single drug clears two serious ones.`;
  const label = (p: ReturnType<typeof pos>, text: string, color: string, mono = false) => (
    <text x={p.x + p.cos * 18} y={p.y + p.sin * 18 + (p.sin > 0.3 ? 8 : p.sin < -0.3 ? 0 : 4)}
      textAnchor={p.cos > 0.3 ? 'start' : p.cos < -0.3 ? 'end' : 'middle'}
      fontSize={11} fill={color} fontFamily={mono ? 'var(--mono)' : 'var(--sans)'}>{text}</text>
  );

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={aria} style={{ display: 'block', maxWidth: width, overflow: 'visible' }}>
      {c.edges.map((e) => {
        const p = at.get(e.a)!, q = at.get(e.b)!;
        // Always drawn, so reviewing the chosen drugs fades the edges out rather than cutting them.
        return (
          <line key={`${e.a}+${e.b}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} className="ag-edge"
            stroke={serious(e.severity) ? 'var(--critical)' : 'var(--ink-3)'}
            strokeWidth={!removed && e.cleared ? 2.5 : serious(e.severity) ? 1.5 : 1}
            style={{ opacity: removed && e.cleared ? 0 : serious(e.severity) ? 1 : 0.55 }}>
            <title>{`${e.a} + ${e.b} (${e.severity})`}</title>
          </line>
        );
      })}
      {order.map((n) => {
        const p = at.get(n)!;
        const chosen = c.chosen.includes(n);
        const gone = removed && chosen;
        return (
          <g key={n}>
            <circle cx={p.x} cy={p.y} r={11} className="ag-node" fill={chosen && !gone ? 'var(--critical)' : 'var(--paper)'}
              stroke={gone ? 'var(--ink-3)' : chosen ? 'var(--critical)' : 'var(--action)'} strokeWidth={1.3} strokeDasharray={gone ? '3 2' : undefined} />
            <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize={9} fontFamily="var(--mono)" fontWeight={500}
              fill={chosen && !gone ? '#fff' : gone ? 'var(--ink-3)' : 'var(--ink)'}>{n.slice(0, 3).toUpperCase()}</text>
            {label(p, gone && !compact ? `${n} (reviewed)` : n, chosen && !gone ? 'var(--critical)' : gone ? 'var(--ink-3)' : 'var(--ink-2)')}
          </g>
        );
      })}
      {unchecked.map((raw, i) => {
        const p = pos(order.length + i);
        return (
          <g key={`${raw}-${i}`}>
            <circle cx={p.x} cy={p.y} r={11} fill="var(--paper)" stroke="var(--warn)" strokeWidth={1.3} strokeDasharray="3 2" />
            <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize={9} fontFamily="var(--mono)" fill="var(--warn)">?</text>
            {label(p, compact ? 'unchecked' : `"${raw}" unchecked`, 'var(--warn)', true)}
          </g>
        );
      })}
    </svg>
  );
}
