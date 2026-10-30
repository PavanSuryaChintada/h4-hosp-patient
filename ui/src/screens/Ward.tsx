// The ward, end to end: a nurse admits a patient and types the list as written, the lab adds
// eGFR, a pharmacist confirms names the system would not guess, a prescriber decides on each
// alert. Every check is the real pipeline, run by tools/serve_ui.py; every permission is
// medsafe.workflow, enforced there. This screen sends what people type and shows the result.

import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth';
import type { AbhaBundle, AlertEvent, Consent, Entry, OverridePattern, WardRecord, WardRow } from '../data/contract';
import { ISSUE_LABEL, PIN_LABEL, pct, plural } from '../data/format';
import { useData } from '../data/load';
import { SERVE_COMMAND, api, useActor, useRecord, useWardUp } from '../data/ward';
import { PatientScreen } from './PatientDetail';
import { Segmented } from '../components/ui';

function ServerDown() {
  return (
    <div className="not-built" role="note">
      <span className="nb-head">The ward needs its local server</span>
      <span>It runs the real pipeline on every patient entered here, and keeps the records and the audit log. From the repo root:
        <span className="mono"> {SERVE_COMMAND}</span>, then open <span className="mono">http://127.0.0.1:8765</span> (or keep using
        <span className="mono"> npm run dev</span>, which forwards to it).</span>
    </div>
  );
}

/** Whether the signed-in role may make an entry, from medsafe.workflow.ENTRIES. */
function useMay() {
  const { x } = useData();
  const { user } = useAuth();
  return (entry: Entry) => !!user && user.key !== 'reviewer' && x.workflow.entries[user.key].includes(entry);
}

function when(iso: string) {
  return new Date(iso).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' });
}

type Queue = 'all' | 'pharmacist' | 'lab';

export function WardList() {
  const up = useWardUp();
  const may = useMay();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const queue = (params.get('queue') as Queue) ?? 'all';
  const [rows, setRows] = useState<WardRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (up) api<WardRow[]>('records').then(setRows).catch((e: Error) => setError(e.message)); }, [up]);
  const shown = useMemo(() => (rows ?? []).filter((r) => queue === 'all'
    || (queue === 'pharmacist' ? r.pharmacist_queue.length > 0 : r.egfr === null)), [rows, queue]);

  return (
    <div className="content">
      <div className="page-head ward-head">
        <div>
          <h1 className="display">Ward</h1>
          <p className="meta">Patients admitted here, checked by the real pipeline on the ward server.</p>
        </div>
        {may('admit') && <Link className="btn btn-primary" to="/app/ward/new">Admit a patient</Link>}
      </div>
      {up === false && <ServerDown />}
      {error && <p className="form-error">{error}</p>}
      {up && rows && (
        <>
          <div className="queue-tools">
            <Segmented label="Queue" value={queue} onChange={(q) => setParams(q === 'all' ? {} : { queue: q })} segments={[
              { value: 'all', label: 'All patients', count: rows.length },
              { value: 'pharmacist', label: 'Pharmacist queue', count: rows.filter((r) => r.pharmacist_queue.length).length },
              { value: 'lab', label: 'Awaiting eGFR', count: rows.filter((r) => r.egfr === null).length },
            ]} />
          </div>
          <div className="panel">
            <table className="t queue">
              <colgroup><col style={{ width: 120 }} /><col style={{ width: 200 }} /><col style={{ width: 80 }} /><col style={{ width: 96 }} /><col style={{ width: 80 }} /><col style={{ width: 96 }} /><col /></colgroup>
              <thead><tr><th>Record</th><th>Admitted</th><th className="num">Age</th><th className="num">eGFR</th><th className="num">Lines</th><th className="num">Actions</th><th>Waiting on</th></tr></thead>
              <tbody>
                {shown.map((r) => {
                  const go = () => navigate(`/app/ward/${r.id}`);
                  return (
                    <tr key={r.id} className="click" tabIndex={0} onClick={go} onKeyDown={(e) => { if (e.key === 'Enter') go(); }}>
                      <td className="mono">{r.id}</td>
                      <td><span className="mono">{when(r.created_at)}</span> <span className="ink-3">{r.created_by}</span></td>
                      <td className="num">{r.age ?? '—'} <span className="ink-3">{r.sex}</span></td>
                      <td className="num">{r.egfr ?? <span className="tag tag-grey">lab</span>}</td>
                      <td className="num">{r.lines}</td>
                      <td className="num">{r.actions}</td>
                      <td className="ink-2">{[...(r.egfr === null ? ['eGFR from the lab'] : []), ...r.pharmacist_queue].join(' · ') || <span className="ink-3">nothing</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {shown.length === 0 && <p className="empty">{rows.length ? 'Nobody in this queue.' : 'No patients admitted yet.'}</p>}
          </div>
        </>
      )}
    </div>
  );
}

const BLANK = { age: '', sex: 'F', weight_kg: '', pregnant: 'N', diagnoses: '', allergies: '', prescriber_count: '1' };

/**
 * The registration-desk ABHA step: request consent, the patient approves, the records arrive.
 * A sandbox: addresses end in @sbx, approval is a button, and the records are synthetic.
 */
function AbhaFetch({ onFetched }: { onFetched: (b: AbhaBundle) => void }) {
  const actor = useActor();
  const [examples, setExamples] = useState<string[]>([]);
  const [address, setAddress] = useState('');
  const [consent, setConsent] = useState<Consent | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<string[]>('abha/examples').then(setExamples).catch(() => setExamples([])); }, []);

  const run = async (step: () => Promise<void>) => { setError(null); try { await step(); } catch (e) { setError((e as Error).message); } };
  const request = () => run(async () => setConsent(await api<Consent>('abha/consents', { actor, address })));
  const approve = () => run(async () => setConsent(await api<Consent>(`abha/consents/${consent!.id}/approve`, { actor: { user: 'patient', role: 'patient' } })));
  const fetchRecords = () => run(async () => onFetched(await api<AbhaBundle>(`abha/consents/${consent!.id}/fetch`, { actor })));

  return (
    <section className="panel abha-fetch" aria-label="Fetch records through ABHA">
      <div className="panel-head">
        <h2 className="section">Fetch records through ABHA</h2>
        <span className="tag tag-grey">Simulated ABHA sandbox · synthetic records · no ABDM connection</span>
      </div>
      <ol className="abha-flow">
        <li className={consent ? 'done' : 'now'}>
          <span className="abha-step">Ask the patient for their ABHA address and request consent</span>
          <div className="role-row">
            <label className="field" style={{ marginTop: 0 }}>
              <span className="label">ABHA address</span>
              <input className="mono" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="name@sbx" disabled={!!consent} />
            </label>
            <button type="button" className="btn btn-primary btn-sm" disabled={!address || !!consent} onClick={request}>Request consent</button>
          </div>
          {!consent && examples.length > 0 && (
            <p className="meta">Sandbox addresses: {examples.map((a) => <button key={a} type="button" className="btn-link mono" onClick={() => setAddress(a)}>{a}</button>).reduce((acc: ReactNode[], el, i) => (i ? [...acc, ' · ', el] : [el]), [])}</p>
          )}
        </li>
        <li className={consent?.status === 'granted' ? 'done' : consent ? 'now' : ''}>
          <span className="abha-step">The patient approves on their phone</span>
          {consent?.status === 'requested' && (
            <div className="role-row">
              <span className="meta">Consent <span className="mono">{consent.id}</span> requested for {consent.purpose}; nothing is shared until the patient approves.</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={approve}>Patient approves (simulated)</button>
            </div>
          )}
          {consent?.status === 'granted' && <span className="meta">Approved; valid until <span className="mono">{new Date(consent.expires_at).toLocaleString('en-GB')}</span>.</span>}
        </li>
        <li className={consent?.status === 'granted' ? 'now' : ''}>
          <span className="abha-step">Fetch the records into the admission form</span>
          {consent?.status === 'granted' && <div className="role-row"><button type="button" className="btn btn-primary btn-sm" onClick={fetchRecords}>Fetch records</button></div>}
        </li>
      </ol>
      {error && <p className="form-error" style={{ padding: '0 16px 16px' }}>{error}</p>}
    </section>
  );
}

export function WardAdmit() {
  const { x, byId } = useData();
  const up = useWardUp();
  const may = useMay();
  const actor = useActor();
  const navigate = useNavigate();
  const location = useLocation();
  const [fields, setFields] = useState<Record<string, string>>(BLANK);
  const [list, setList] = useState<string>((location.state as { medication_list?: string } | null)?.medication_list ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fetched, setFetched] = useState<AbhaBundle | null>(null);
  const fromAbha = (b: AbhaBundle) => { setFields(b.fields); setList(b.medication_list); setFetched(b); };
  const set = (k: string) => (e: { target: { value: string } }) => setFields((f) => ({ ...f, [k]: e.target.value }));

  const startFrom = (id: string) => {
    const p = byId.get(id);
    if (!p) return;
    setFields({ age: String(p.age ?? ''), sex: p.sex ?? 'F', weight_kg: String(p.weight_kg ?? ''),
      pregnant: p.pregnant === null ? 'NA' : p.pregnant ? 'Y' : 'N', diagnoses: p.diagnoses.join('; '),
      allergies: p.allergies ?? '', prescriber_count: String(p.prescriber_count ?? 1) });
    setList(p.medications.map((m) => m.raw).join('\n'));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const record = await api<WardRecord>('records', { actor, fields, medication_list: list, consent_id: fetched?.consent.id });
      navigate(`/app/ward/${record.id}`);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };

  if (!may('admit')) {
    return <div className="content"><h1 className="display">Admit a patient</h1><p className="empty" style={{ marginTop: 16 }}>A ward nurse admits patients. Sign in as the ward nurse to enter one.</p></div>;
  }
  return (
    <div className="content" style={{ maxWidth: 1080 }}>
      <div className="page-head">
        <h1 className="display">Admit a patient</h1>
        <p className="meta">Copy everything the patient brought, exactly as written. eGFR comes from the lab after admission.</p>
      </div>
      {up === false && <ServerDown />}
      {may('abha_pull') && up && <AbhaFetch onFetched={fromAbha} />}
      {fetched && (
        <p className="abha-filled" role="status">
          Prefilled from ABHA consent <span className="mono">{fetched.consent.id}</span> ({fetched.source}). Check it with the patient and add
          anything they brought that the records do not have.{fetched.lab.egfr && <> The records hold an eGFR of <span className="mono">{fetched.lab.egfr}</span>: the lab confirms it after admission.</>}
        </p>
      )}
      {x.demo && (
        <div className="admit-seed">
          <span className="meta">Start from a training-set patient:</span>
          {x.demo.pins.flatMap((p) => p.patient_ids.map((id) => (
            <button key={id} type="button" className="btn-link" onClick={() => startFrom(id)}>{PIN_LABEL[p.slot]} (<span className="mono">{id}</span>)</button>
          )))}
        </div>
      )}
      <form className="panel admit" onSubmit={submit}>
        <div className="admit-grid">
          <label className="field"><span className="label">Age</span><input inputMode="numeric" required value={fields.age} onChange={set('age')} /></label>
          <label className="field"><span className="label">Sex</span>
            <select value={fields.sex} onChange={set('sex')}><option value="F">Female</option><option value="M">Male</option></select></label>
          <label className="field"><span className="label">Weight (kg)</span><input inputMode="decimal" value={fields.weight_kg} onChange={set('weight_kg')} /></label>
          <label className="field"><span className="label">Pregnant</span>
            <select value={fields.pregnant} onChange={set('pregnant')}><option value="N">No</option><option value="Y">Yes</option><option value="NA">Not applicable</option></select></label>
          <label className="field"><span className="label">Prescribers whose slips are on the list</span>
            <select value={fields.prescriber_count} onChange={set('prescriber_count')}>{['1', '2', '3'].map((n) => <option key={n}>{n}</option>)}</select></label>
          <label className="field admit-wide"><span className="label">Diagnoses, as written (separate with ;)</span><input value={fields.diagnoses} onChange={set('diagnoses')} /></label>
          <label className="field admit-wide"><span className="label">Allergies, as written</span><input value={fields.allergies} onChange={set('allergies')} placeholder="NKDA, or the allergy as the patient states it" /></label>
        </div>
        <label className="field">
          <span className="label">Medication list, one line per medicine, exactly as on the slips, strips and bottles</span>
          <textarea className="mono" rows={10} required value={list} onChange={(e) => setList(e.target.value)} spellCheck={false} />
        </label>
        {error && <p className="form-error">{error}</p>}
        <div className="intake-actions">
          <button type="submit" className="btn btn-primary" disabled={busy || up === false}>{busy ? 'Checking' : 'Admit and run the check'}</button>
          <span className="meta">The ward server runs the same pipeline as <span className="mono">run.py</span> on this record.</span>
        </div>
      </form>
    </div>
  );
}

/** What the signed-in role does on this record, from medsafe.workflow.ENTRIES. */
function RolePanel({ r, send }: { r: WardRecord; send: (action: string, body: object) => Promise<boolean> }) {
  const { x } = useData();
  const { user } = useAuth();
  const may = useMay();
  const actor = useActor();
  const [egfr, setEgfr] = useState(r.egfr ?? r.abha_egfr ?? '');
  const [list, setList] = useState(r.lines.map((l) => l.raw).join('\n'));
  const [editing, setEditing] = useState(false);
  const [names, setNames] = useState<Record<number, string>>({});
  const unresolved = r.result.medications.filter((m) => m.status === 'unresolved');
  const waiting = Object.values(r.alert_states).filter((e) => e.event === 'defer' || e.event === 'escalate');

  return (
    <section className="role-panel" aria-label="Your part">
      <div className="role-head">
        <span className="role-k">{user?.role}</span>
        <span className="meta">Record <span className="mono">{r.id}</span>, admitted <span className="mono">{when(r.created_at)}</span> by {r.created_by}</span>
        {r.source?.kind === 'abha_sandbox' && (
          <span className="tag tag-grey">List started from ABHA consent <span className="mono">{r.source.consent_id}</span> · simulated sandbox</span>
        )}
      </div>

      {may('egfr') && (
        <form className="role-row" onSubmit={async (e) => { e.preventDefault(); await send('egfr', { actor, egfr }); }}>
          <label className="field" style={{ marginTop: 0 }}>
            <span className="label">eGFR (mL/min/1.73m²)</span>
            <input inputMode="decimal" value={egfr} onChange={(e) => setEgfr(e.target.value)} />
          </label>
          <button type="submit" className="btn btn-primary">{r.egfr ? 'Update eGFR and re-run' : 'Record eGFR and re-run'}</button>
          <span className="meta">
            {!r.egfr && r.abha_egfr ? <>Prefilled from the ABHA records ({r.abha_egfr}): confirm it against the latest result before recording. </> : null}
            The kidney-dose rules re-run on the value you record.
          </span>
        </form>
      )}

      {may('confirm_name') && (
        unresolved.length === 0 ? <p className="meta">No line is waiting for a name.</p> : (
          <div className="role-confirm">
            <p className="trust-h">Lines the system would not guess</p>
            <datalist id="generics">{x.workflow.generics.map((g) => <option key={g} value={g} />)}</datalist>
            {unresolved.map((m) => (
              <form key={m.index} className="role-row" onSubmit={async (e) => {
                e.preventDefault();
                await send('confirm', { actor, line: m.index, generics: (names[m.index] ?? '').split('+').map((g) => g.trim()).filter(Boolean) });
              }}>
                <span className="mono role-raw">"{m.raw}"</span>
                <label className="field" style={{ marginTop: 0 }}>
                  <span className="label">Generic(s), from the drug reference; join two with +</span>
                  <input list="generics" value={names[m.index] ?? ''} onChange={(e) => setNames((n) => ({ ...n, [m.index]: e.target.value }))} />
                </label>
                <button type="submit" className="btn btn-primary btn-sm">Confirm and re-run</button>
              </form>
            ))}
          </div>
        )
      )}

      {user?.key === 'pharmacist' && waiting.length > 0 && (
        <p className="meta">{plural(waiting.length, 'alert')} deferred or escalated to you: {waiting.map((e) => e.alert).join(', ')}. Decide on them below.</p>
      )}

      {may('medication_list') && (
        editing ? (
          <form className="role-list" onSubmit={async (e) => { e.preventDefault(); if (await send('medication_list', { actor, medication_list: list })) setEditing(false); }}>
            <label className="field" style={{ marginTop: 0 }}>
              <span className="label">Medication list, as written</span>
              <textarea className="mono" rows={8} value={list} onChange={(e) => setList(e.target.value)} spellCheck={false} />
            </label>
            <div className="handoff-actions">
              <button type="submit" className="btn btn-primary btn-sm">Save and re-run</button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </form>
        ) : <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>Edit the medication list</button>
      )}

      {user?.key === 'prescriber' && <p className="meta">Decide on each action below: accept it, override it with a reason, or defer it to the pharmacist.</p>}
      {user?.key === 'reviewer' && <p className="meta">Read-only: the reviewer role makes no entries and no decisions.</p>}

      <details className="role-history">
        <summary>Record history ({r.history.length + r.events.filter((e) => e.event !== 'shown').length})</summary>
        <ol>
          {[...r.history.map((h) => ({ at: h.at, who: `${h.user}, ${h.role}`, what: `${h.entry.replace('_', ' ')}: ${h.detail}` })),
            ...r.events.filter((e) => e.event !== 'shown').map((e) => ({ at: e.timestamp, who: `${e.user}, ${e.role}`, what: `${e.event} ${e.alert}${e.reason ? ` (${e.reason})` : ''}${e.note ? `: ${e.note}` : ''}` }))]
            .sort((a, b) => a.at.localeCompare(b.at))
            .map((h, i) => <li key={i}><span className="mono">{when(h.at)}</span> · {h.who} · {h.what}</li>)}
        </ol>
      </details>
    </section>
  );
}

export function WardRecordScreen() {
  const { id = '' } = useParams();
  const up = useWardUp();
  const actor = useActor();
  const { x } = useData();
  const { record, error, send, setError } = useRecord(id);
  const sent = useRef(new Set<string>());

  // Log that each submitted alert was shown to this clinician, once (medsafe.workflow EVENTS "shown").
  useEffect(() => {
    if (!record || !actor || !['prescriber', 'pharmacist'].includes(actor.role)) return;
    const seen = new Set(record.events.filter((e) => e.event === 'shown' && e.user === actor.user).map((e) => e.alert));
    const unseen = (record.result.medsafe.alerts ?? []).filter((a) => a.submitted && !seen.has(a.key) && !sent.current.has(a.key));
    if (unseen.length === 0) return;
    unseen.forEach((a) => sent.current.add(a.key));
    Promise.all(unseen.map((a) => api(`records/${id}/events`, { actor, alert: a.key, event: 'shown' })))
      .catch((e: Error) => setError(e.message));
  }, [record, actor, id, setError]);

  if (up === false) return <div className="content"><ServerDown /></div>;
  if (!record) return <div className="content">{error ? <p className="empty">{error}</p> : <p className="empty">Reading the record</p>}</div>;

  const d = { states: record.alert_states, onEvent: (alert: string, event: AlertEvent, reason?: string, note?: string) => send('events', { actor, alert, event, reason, note }) };
  const trust = { requested: record.review_requested, history: record.history, onRequest: (note: string) => send('review', { actor, note }) };
  return (
    <PatientScreen p={record.result} ward={{ d, trust }}
      top={<>{error && <p className="form-error" role="alert">{error}</p>}<RolePanel r={record} send={send} /><p className="meta ward-disclaimer">{x.workflow.disclaimer}</p></>} />
  );
}

export function Patterns() {
  const up = useWardUp();
  const [rows, setRows] = useState<OverridePattern[] | null>(null);
  useEffect(() => { if (up) api<OverridePattern[]>('patterns').then(setRows).catch(() => setRows([])); }, [up]);
  return (
    <div className="content" style={{ maxWidth: 1080 }}>
      <div className="page-head">
        <h1 className="display">Override patterns</h1>
        <p className="meta">Which kinds of alert the ward overrides most, and why, from the audit log. A rule overridden for the same reason again and again is a rule to review, not a clinician to retrain.</p>
      </div>
      {up === false && <ServerDown />}
      {rows && (
        <div className="panel">
          <table className="t">
            <thead><tr><th>Issue type</th><th className="num">Shown</th><th className="num">Overridden</th><th className="num">Rate</th><th>Reasons, most common first</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.issue_type}>
                  <th scope="row">{ISSUE_LABEL[r.issue_type] ?? r.issue_type}</th>
                  <td className="num">{r.shown}</td><td className="num">{r.overridden}</td><td className="num">{pct(r.rate)}</td>
                  <td className="ink-2">{r.reasons.map(([reason, n]) => `${reason} (${n})`).join(' · ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="empty">No alert has been shown or overridden on the ward yet.</p>}
        </div>
      )}
    </div>
  );
}
