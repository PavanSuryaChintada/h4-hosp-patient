// The ward, end to end: a nurse admits a patient and types the list as written, the lab adds
// eGFR, a pharmacist confirms names the system would not guess, a prescriber decides on each
// alert. Every check is the real pipeline, run by tools/serve_ui.py; every permission is
// medsafe.workflow, enforced there. This screen sends what people type and shows the result,
// and says in a toast what each re-run changed.

import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { DEMO_USERS, useAuth, type RoleKey } from '../auth';
import type { AbhaBundle, AlertEvent, Consent, Entry, OverridePattern, PatientView, WardRecord, WardRow, WardTask } from '../data/contract';
import { ISSUE_LABEL, PIN_LABEL, pct, plural } from '../data/format';
import { useData } from '../data/load';
import { DEMO_COMMAND, SERVE_COMMAND, api, useActor, useRecord, useWard, useWardUp } from '../data/ward';
import { PatientScreen } from './PatientDetail';
import { Modal } from '../components/Modal';
import { ROLE, RoleName, RoleTile } from '../components/Roles';
import { useSwitchRole } from '../components/Shell';
import { useToast, type Tone, type ToastInput } from '../components/Toast';
import { Segmented, StatusCell } from '../components/ui';
import { Icon, Meter } from '../components/viz';
import { QuickFill } from '../components/QuickFill';
import { ADD_LINE_EXAMPLES, DEMO_PATIENTS, EGFR_EXAMPLES, type DemoPatient } from '../data/examples';

function ServerDown() {
  return (
    <div className="server-down" role="note">
      <p className="status-line tone-fail"><span className="sq" aria-hidden="true" /><strong>The ward server is not running here</strong></p>
      <p>The ward runs the real Python pipeline on every patient typed in, and keeps the records and the audit log, so it needs its local server.</p>
      <ol>
        <li>On the demo laptop, double-click <span className="mono">{DEMO_COMMAND}</span> in the repo folder (or run <span className="mono">{SERVE_COMMAND} --fresh --open</span>).</li>
        <li>It builds the app, starts the server and opens <span className="mono">http://127.0.0.1:8765/login</span>.</li>
      </ol>
      <p className="meta">Everything under Training data works without it, including decisions on the training-set patients. <Link to="/app?demo=1">Open the patient queue →</Link></p>
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

/** The colour of a task for whoever is looking: your turn, with the pharmacist, or waiting on someone. */
function taskTone(t: WardTask, me: RoleKey | undefined): Tone {
  if (t.role === me) return 'turn';
  return t.kind === 'answer' || t.kind === 'review' ? 'handed' : 'wait';
}

export function TaskTag({ t, me }: { t: WardTask; me: RoleKey | undefined }) {
  const tone = taskTone(t, me);
  return (
    <span className={`task-tag status-line tone-${tone}`}>
      <span className="sq" aria-hidden="true" />
      {tone === 'turn' ? <strong>Your turn:</strong> : <span className="task-who">{ROLE[t.role].title}:</span>} {t.text}
    </span>
  );
}

/** What changed between two checks of the same record, as a toast. Compares exported results only. */
function rerun(title: string, before: PatientView, after: PatientView): ToastInput {
  const was = new Map((before.medsafe.alerts ?? []).filter((a) => a.submitted).map((a) => [a.key, a]));
  const now = new Map((after.medsafe.alerts ?? []).filter((a) => a.submitted).map((a) => [a.key, a]));
  const added = [...now.values()].filter((a) => !was.has(a.key));
  const cleared = [...was.values()].filter((a) => !now.has(a.key));
  const moved = [...now.values()].filter((a) => was.has(a.key) && was.get(a.key)!.severity !== a.severity);
  const name = (a: { drugs: string[]; issue_type: keyof typeof ISSUE_LABEL }) => `${a.drugs.join(' + ')} ${ISSUE_LABEL[a.issue_type].toLowerCase()}`;
  const parts = [`Checks re-ran: ${after.compare.medsafe.actions ?? 0} action(s), was ${before.compare.medsafe.actions ?? 0}.`];
  if (added.length) parts.push(`New: ${added.map((a) => `${name(a)} (${a.severity})`).join(', ')}.`);
  if (moved.length) parts.push(`Changed: ${moved.map((a) => `${name(a)} ${was.get(a.key)!.severity} to ${a.severity}`).join(', ')}.`);
  if (cleared.length) parts.push(`Cleared: ${cleared.map(name).join(', ')}.`);
  if (!added.length && !moved.length && !cleared.length) parts.push('No alert changed.');
  const serious = [...added, ...moved].some((a) => a.severity === 'contraindicated' || a.severity === 'major');
  return { tone: serious ? 'danger' : 'done', title, body: parts.join(' ') };
}

type Queue = 'mine' | 'all' | 'done';

export function WardList() {
  const { up, rows } = useWard();
  const { user } = useAuth();
  const may = useMay();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const me = user?.key;
  const mineOf = (r: WardRow) => r.tasks.some((t) => t.role === me);
  const queue = (params.get('queue') as Queue | null) ?? (me && me !== 'reviewer' && me !== 'nurse' ? 'mine' : 'all');
  const shown = useMemo(() => (rows ?? []).filter((r) => queue === 'all' || (queue === 'done' ? r.tasks.length === 0 : mineOf(r))),
    [rows, queue, me]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="content">
      <div className="page-head ward-head">
        <div>
          <h1 className="display">Ward patients</h1>
          <p className="meta">Patients admitted on this ward, checked by the real pipeline on the ward server. The list refreshes on its own, so each role sees the others' work.</p>
        </div>
        {may('admit') && <Link className="btn btn-turn" to="/app/ward/new"><Icon name="person" size={16} />Admit a patient</Link>}
      </div>
      {up === false && <ServerDown />}
      {up && rows && (
        <>
          <div className="queue-tools">
            <Segmented label="Which records" value={queue} onChange={(q) => setParams({ queue: q })} segments={[
              ...(me && me !== 'reviewer' ? [{ value: 'mine' as Queue, label: 'Waiting on me', count: rows.filter(mineOf).length }] : []),
              { value: 'all', label: 'All patients', count: rows.length },
              { value: 'done', label: 'Nothing waiting', count: rows.filter((r) => r.tasks.length === 0).length },
            ]} />
          </div>
          <div className="panel">
            <table className="t queue ward-table">
              <colgroup><col style={{ width: 112 }} /><col style={{ width: 176 }} /><col style={{ width: 80 }} /><col style={{ width: 72 }} /><col style={{ width: 152 }} /><col style={{ width: 232 }} /><col /></colgroup>
              <thead><tr><th>Record</th><th>Admitted</th><th className="num">Age</th><th className="num">eGFR</th><th>Most severe</th><th>Decisions</th><th>Status</th></tr></thead>
              <tbody>
                {shown.map((r) => {
                  const go = () => navigate(`/app/ward/${r.id}`);
                  const d = r.decisions;
                  return (
                    <tr key={r.id} className={`click${mineOf(r) ? ' row-mine' : ''}`} tabIndex={0} onClick={go} onKeyDown={(e) => { if (e.key === 'Enter') go(); }}>
                      <td className="mono">{r.id}</td>
                      <td><span className="mono">{when(r.created_at)}</span> <span className="ink-3">{r.created_by}</span></td>
                      <td className="num">{r.age ?? '—'} <span className="ink-3">{r.sex}</span></td>
                      <td className="num">{r.egfr ?? <span className="ink-3">—</span>}</td>
                      {r.top_severity && r.top_severity !== 'none' ? <StatusCell severity={r.top_severity} /> : <td className="ink-3">no alert sent</td>}
                      <td>{d.submitted ? <span className="dec-cell"><Meter value={d.decided} max={d.submitted} width={56} height={6} color="var(--ok)" /><span className="mono">{d.decided}/{d.submitted}</span>{d.handed > 0 && <span className="handed-n">+{d.handed} with pharmacist</span>}</span> : <span className="ink-3">none needed</span>}</td>
                      <td className="task-cell">
                        {r.tasks.length === 0
                          ? <span className="task-tag status-line tone-done"><span className="sq" aria-hidden="true" />Nothing waiting: every alert decided</span>
                          : r.tasks.map((t) => <TaskTag key={t.kind} t={t} me={me} />)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {shown.length === 0 && (
              <p className="empty">{rows.length === 0 ? (may('admit') ? 'No patients yet. Admit the first one.' : 'No patients yet. The ward nurse admits the first one.') : queue === 'mine' ? 'Nothing is waiting on you.' : 'No record here.'}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

const BLANK = { age: '', sex: 'F', weight_kg: '', pregnant: 'N', diagnoses: '', allergies: '', prescriber_count: '1' };

/** The patient's phone in the ABHA sandbox: the consent request as they would see it. */
function PhoneConsent({ consent, onApprove, onDeny }: { consent: Consent; onApprove: () => void; onDeny: () => void }) {
  return (
    <Modal tone="turn" kicker="Simulated ABHA sandbox" title="The patient's phone" onClose={onDeny}>
      <div className="phone">
        <div className="phone-bar"><Icon name="phone" size={14} />ABHA app · <span className="mono">{consent.address}</span></div>
        <div className="phone-body">
          <p className="phone-k">Consent request</p>
          <p className="phone-h">{consent.requested_by} at the ward asks to see your health records</p>
          <dl className="phone-dl">
            <div><dt>Purpose</dt><dd>{consent.purpose}</dd></div>
            <div><dt>Records</dt><dd>Prescriptions, diagnoses, lab results</dd></div>
            <div><dt>Valid until</dt><dd className="mono">{new Date(consent.expires_at).toLocaleString('en-GB')}</dd></div>
            <div><dt>Request</dt><dd className="mono">{consent.id}</dd></div>
          </dl>
          <div className="phone-actions">
            <button type="button" className="btn btn-done btn-block" onClick={onApprove}>Approve</button>
            <button type="button" className="btn btn-secondary btn-block" onClick={onDeny}>Not now</button>
          </div>
        </div>
      </div>
      <p className="meta" style={{ marginTop: 12 }}>A sandbox: addresses end in <span className="mono">@sbx</span>, approval is this button, and the records are one synthetic patient from the pack's test split. Nothing connects to ABDM.</p>
    </Modal>
  );
}

/**
 * The registration-desk ABHA step: request consent, the patient approves, the records arrive.
 * A sandbox: addresses end in @sbx, approval is a button, and the records are synthetic.
 */
function AbhaFetch({ onFetched }: { onFetched: (b: AbhaBundle) => void }) {
  const actor = useActor();
  const toast = useToast();
  const [examples, setExamples] = useState<string[]>([]);
  const [address, setAddress] = useState('');
  const [consent, setConsent] = useState<Consent | null>(null);
  const [phone, setPhone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<string[]>('abha/examples').then(setExamples).catch(() => setExamples([])); }, []);

  const run = async (step: () => Promise<void>) => { setError(null); try { await step(); } catch (e) { setError((e as Error).message); toast({ tone: 'fail', title: 'That did not go through', body: (e as Error).message }); } };
  const request = () => run(async () => {
    const c = await api<Consent>('abha/consents', { actor, address });
    setConsent(c);
    setPhone(true);
    toast({ tone: 'wait', title: `Consent ${c.id} sent to the patient`, body: 'Nothing is shared until the patient approves on their phone.' });
  });
  const approve = () => run(async () => {
    setPhone(false);
    setConsent(await api<Consent>(`abha/consents/${consent!.id}/approve`, { actor: { user: 'patient', role: 'patient' } }));
    toast({ tone: 'done', title: 'The patient approved', body: 'Fetch the records into the admission form.' });
  });
  const fetchRecords = () => run(async () => {
    const b = await api<AbhaBundle>(`abha/consents/${consent!.id}/fetch`, { actor });
    onFetched(b);
    toast({ tone: 'done', title: 'Records fetched through ABHA', body: `${plural(b.medication_list.split('\n').filter(Boolean).length, 'medicine line')} and the patient's details are in the form below. Check them with the patient.` });
  });

  const step = !consent ? 0 : consent.status !== 'granted' ? 1 : 2;
  return (
    <section className="panel abha-fetch" aria-label="Fetch records through ABHA">
      <div className="panel-head">
        <h2 className="section">Step 1 (optional): fetch records through ABHA</h2>
        <span className="tag tag-grey">Simulated ABHA sandbox · synthetic records · no ABDM connection</span>
      </div>
      <ol className="abha-flow">
        <li className={step > 0 ? 'done' : 'now'}>
          <span className="abha-step">Ask the patient for their ABHA address and request consent</span>
          <div className="role-row">
            <label className="field" style={{ marginTop: 0 }}>
              <span className="label">ABHA address</span>
              <input className="mono" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="name@sbx" disabled={!!consent} />
            </label>
            <button type="button" className="btn btn-turn btn-sm" disabled={!address || !!consent} onClick={request}>Request consent</button>
          </div>
          {!consent && <QuickFill label="Sandbox addresses" picks={examples.map((a) => ({ label: a, onPick: () => setAddress(a) }))} />}
        </li>
        <li className={step > 1 ? 'done' : step === 1 ? 'now' : ''}>
          <span className="abha-step">The patient approves on their phone</span>
          {step === 1 && (
            <div className="role-row">
              <span className="status-line tone-wait"><span className="sq" aria-hidden="true" />Waiting for the patient: consent <span className="mono">{consent!.id}</span></span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setPhone(true)}><Icon name="phone" size={14} />Show the patient's phone</button>
            </div>
          )}
          {step === 2 && <span className="meta">Approved; valid until <span className="mono">{new Date(consent!.expires_at).toLocaleString('en-GB')}</span>.</span>}
        </li>
        <li className={step === 2 ? 'now' : ''}>
          <span className="abha-step">Fetch the records into the admission form</span>
          {step === 2 && <div className="role-row"><button type="button" className="btn btn-turn btn-sm" onClick={fetchRecords}>Fetch records</button></div>}
        </li>
      </ol>
      {error && <p className="form-error" style={{ padding: '0 16px 16px' }}>{error}</p>}
      {phone && consent && consent.status !== 'granted' && <PhoneConsent consent={consent} onApprove={approve} onDeny={() => setPhone(false)} />}
    </section>
  );
}

export function WardAdmit() {
  const { x, byId } = useData();
  const { up, refresh } = useWard();
  const may = useMay();
  const actor = useActor();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [fields, setFields] = useState<Record<string, string>>(BLANK);
  const [list, setList] = useState<string>((location.state as { medication_list?: string } | null)?.medication_list ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fetched, setFetched] = useState<AbhaBundle | null>(null);
  const fromAbha = (b: AbhaBundle) => { setFields(b.fields); setList(b.medication_list); setFetched(b); };
  const set = (k: string) => (e: { target: { value: string } }) => setFields((f) => ({ ...f, [k]: e.target.value }));

  const startFrom = (id: string, label: string) => {
    const p = byId.get(id);
    if (!p) return;
    setFields({ age: String(p.age ?? ''), sex: p.sex ?? 'F', weight_kg: String(p.weight_kg ?? ''),
      pregnant: p.pregnant === null ? 'NA' : p.pregnant ? 'Y' : 'N', diagnoses: p.diagnoses.join('; '),
      allergies: p.allergies ?? '', prescriber_count: String(p.prescriber_count ?? 1) });
    setList(p.medications.map((m) => m.raw).join('\n'));
    toast({ tone: 'done', title: `Form filled from ${id}`, body: `${label}: ${plural(p.medications.length, 'line')} as written. eGFR stays the lab's entry.` });
  };

  const fillDemo = (d: DemoPatient) => {
    setFields(d.fields);
    setList(d.medication_list);
    setFetched(null);
    toast({ tone: 'done', title: `Form filled: ${d.label.split(':')[0]}`, body: 'Check the form below, then press "Admit and run the check".' });
    document.querySelector('.admit')?.scrollIntoView({ block: 'start' });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const record = await api<WardRecord>('records', { actor, fields, medication_list: list, consent_id: fetched?.consent.id });
      await refresh();
      const m = record.result.compare.medsafe;
      toast({
        tone: 'done', title: `${record.id} admitted and checked`,
        body: `The pipeline read ${m.checked} of ${m.lines} lines and found ${plural(m.actions ?? 0, 'action')}. Waiting now: ${record.tasks.map((t) => `${ROLE[t.role].title} (${t.text})`).join(', ') || 'nobody'}.`,
      });
      navigate(`/app/ward/${record.id}`);
    } catch (err) {
      setError((err as Error).message);
      toast({ tone: 'fail', title: 'The record was not saved', body: (err as Error).message });
    } finally { setBusy(false); }
  };

  if (!may('admit')) {
    const nurse = DEMO_USERS.find((u) => u.key === 'nurse')!;
    return <div className="content"><h1 className="display">Admit a patient</h1><SwitchHint role="nurse" text={`A ward nurse admits patients. Sign in as ${nurse.name} to enter one.`} /></div>;
  }
  return (
    <div className="content" style={{ maxWidth: 1080 }}>
      <div className="page-head">
        <h1 className="display">Admit a patient</h1>
        <p className="meta">Copy everything the patient brought, exactly as written. eGFR comes from the lab after admission.</p>
      </div>
      {up === false && <ServerDown />}
      <section className="demo-patients" aria-label="Demo patients">
        <p className="quick-k"><Icon name="bolt" size={14} />Quick fill for the demo: one click fills the whole form</p>
        <div className="demo-cards">
          {DEMO_PATIENTS.map((d) => (
            <button key={d.label} type="button" className="demo-card" onClick={() => fillDemo(d)}>
              <strong>{d.label}</strong>
              <span>{d.story}</span>
              <span className="demo-card-go">Fill the form →</span>
            </button>
          ))}
        </div>
      </section>
      {may('abha_pull') && up && <AbhaFetch onFetched={fromAbha} />}
      {fetched && (
        <p className="abha-filled status-line tone-done" role="status">
          <span className="sq" aria-hidden="true" />
          <span>Prefilled from ABHA consent <span className="mono">{fetched.consent.id}</span> ({fetched.source}). Check it with the patient and add
          anything they brought that the records do not have.{fetched.lab.egfr && <> The records hold an eGFR of <span className="mono">{fetched.lab.egfr}</span>: the lab confirms it after admission.</>}</span>
        </p>
      )}
      {x.demo && (
        <div className="admit-seed">
          <span className="meta">Or copy a training-set patient:</span>
          {x.demo.pins.flatMap((p) => p.patient_ids.map((id) => (
            <button key={id} type="button" className="btn btn-secondary btn-sm" onClick={() => startFrom(id, PIN_LABEL[p.slot])}>{PIN_LABEL[p.slot]} <span className="mono ink-3">{id}</span></button>
          )))}
        </div>
      )}
      <form className="panel admit" onSubmit={submit}>
        <h2 className="section admit-h">Step 2: the patient and the list as written</h2>
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
          <button type="submit" className="btn btn-turn" disabled={busy || up === false || !list.trim() || !fields.age}>{busy ? 'Checking' : 'Admit and run the check'}</button>
          <span className="meta">The ward server runs the same pipeline as <span className="mono">run.py</span> on this record.</span>
        </div>
      </form>
    </div>
  );
}

/** When it is someone else's turn: who, and (in the demo) a button to become them. */
function SwitchHint({ role, text }: { role: RoleKey; text: string }) {
  const switchTo = useSwitchRole();
  const { user } = useAuth();
  const u = DEMO_USERS.find((d) => d.key === role)!;
  return (
    <div className="switch-hint status-line tone-wait">
      <span className="sq" aria-hidden="true" />
      <span>{text}</span>
      {user?.key !== role && <button type="button" className="btn btn-secondary btn-sm" onClick={() => switchTo(u)}><RoleTile role={role} size={20} />Sign in as {u.name}</button>}
    </div>
  );
}

type Step = { role: RoleKey; title: string; detail: string; state: 'done' | 'todo' | 'handed' | 'idle' };

/** The record's path round the ward: who has done their part, whose turn it is. */
function CarePath({ r }: { r: WardRecord }) {
  const { user } = useAuth();
  const unresolved = r.result.medications.filter((m) => m.status === 'unresolved').length;
  const confirmed = r.lines.filter((l) => l.confirmed).length;
  const d = r.decisions;
  const steps: Step[] = [
    { role: 'nurse', title: 'Admitted', state: 'done', detail: `${r.created_by}, ${when(r.created_at)}${r.source ? ', from ABHA' : ''}` },
    { role: 'lab', title: 'eGFR', state: r.egfr ? 'done' : 'todo', detail: r.egfr ? `eGFR ${r.egfr} recorded` : 'not entered yet' },
    { role: 'pharmacist', title: 'Names', state: unresolved ? 'todo' : 'done', detail: unresolved ? `${plural(unresolved, 'line')} to confirm` : confirmed ? `${confirmed} confirmed by the pharmacist` : 'every line read' },
    { role: 'prescriber', title: 'Decisions', state: d.undecided ? 'todo' : 'done', detail: d.submitted ? `${d.decided} of ${d.submitted} decided` : 'no alert to decide' },
    { role: 'pharmacist', title: 'Handed over', state: d.handed || r.review_requested ? 'handed' : 'idle', detail: d.handed || r.review_requested ? [d.handed ? plural(d.handed, 'alert') : '', r.review_requested ? 'review requested' : ''].filter(Boolean).join(', ') : 'only if an alert is deferred' },
  ];
  const tone = (s: Step): Tone | 'idle' => (s.state === 'done' ? 'done' : s.state === 'idle' ? 'idle' : s.role === user?.key ? 'turn' : s.state === 'handed' ? 'handed' : 'wait');
  const label = (s: Step) => {
    const t = tone(s);
    return t === 'done' ? 'Done' : t === 'turn' ? 'Your turn' : t === 'handed' ? 'With the pharmacist' : t === 'idle' ? 'Not needed' : `Waiting on ${ROLE[s.role].title.toLowerCase()}`;
  };
  return (
    <ol className="care-path" aria-label="Where this record is on the ward">
      {steps.map((s, i) => (
        <li key={s.title} className={`cp-step tone-${tone(s)}`}>
          <div className="cp-top"><span className="cp-n mono">{i + 1}</span><RoleTile role={s.role} size={24} /><span className="cp-state">{label(s)}</span></div>
          <strong>{s.title}</strong>
          <span className="cp-detail">{s.detail}</span>
        </li>
      ))}
    </ol>
  );
}

/** What the signed-in role does on this record, from medsafe.workflow.ENTRIES. */
function RolePanel({ r, send }: { r: WardRecord; send: (action: string, body: object) => Promise<WardRecord | null> }) {
  const { x } = useData();
  const { user } = useAuth();
  const may = useMay();
  const actor = useActor();
  const toast = useToast();
  const [egfr, setEgfr] = useState(r.egfr ?? r.abha_egfr ?? '');
  const [list, setList] = useState(r.lines.map((l) => l.raw).join('\n'));
  const [editing, setEditing] = useState(false);
  const [names, setNames] = useState<Record<number, string>>({});
  const unresolved = r.result.medications.filter((m) => m.status === 'unresolved');
  const mine = r.tasks.filter((t) => t.role === user?.key);
  const next = r.tasks.find((t) => t.role !== user?.key);

  const act = async (title: string, action: string, body: object) => {
    const after = await send(action, body);
    if (after) toast(rerun(title, r.result, after.result));
    return !!after;
  };

  return (
    <section className={`role-panel ${mine.length ? 'tone-turn' : 'tone-quiet'}`} aria-label="Your part">
      <div className="role-head">
        {user && <RoleTile role={user.key} size={32} />}
        <div>
          <p className="role-k">{mine.length ? `Your turn, ${user?.role.toLowerCase()}` : `${user?.role}: nothing waiting on you here`}</p>
          <p className="meta">{mine.length ? mine.map((t) => t.text).join(' · ') : r.tasks.length === 0 ? 'Every alert on this record is decided.' : 'The record is with someone else for now.'}</p>
        </div>
        {r.source?.kind === 'abha_sandbox' && (
          <span className="tag tag-grey">List started from ABHA consent <span className="mono">{r.source.consent_id}</span> · simulated sandbox</span>
        )}
      </div>

      {may('egfr') && (
        <form className="role-row" onSubmit={async (e) => { e.preventDefault(); await act(`eGFR ${egfr} recorded`, 'egfr', { actor, egfr }); }}>
          <label className="field" style={{ marginTop: 0 }}>
            <span className="label">eGFR (mL/min/1.73m²)</span>
            <input inputMode="decimal" value={egfr} onChange={(e) => setEgfr(e.target.value)} />
          </label>
          <button type="submit" className="btn btn-turn" disabled={!String(egfr).trim()}>{r.egfr ? 'Update eGFR and re-run' : 'Record eGFR and re-run'}</button>
          <QuickFill picks={EGFR_EXAMPLES.map((ex) => ({ label: ex.label, title: ex.hint, onPick: () => setEgfr(ex.value) }))} />
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
                const generics = (names[m.index] ?? '').split('+').map((g) => g.trim()).filter(Boolean);
                await act(`"${m.raw}" confirmed as ${generics.join(' + ')}`, 'confirm', { actor, line: m.index, generics });
              }}>
                <span className="mono role-raw">"{m.raw}"</span>
                <label className="field" style={{ marginTop: 0 }}>
                  <span className="label">Generic(s), from the drug reference; join two with +</span>
                  <input list="generics" value={names[m.index] ?? ''} onChange={(e) => setNames((n) => ({ ...n, [m.index]: e.target.value }))} />
                </label>
                <button type="submit" className="btn btn-turn btn-sm" disabled={!(names[m.index] ?? '').trim()}>Confirm and re-run</button>
                <QuickFill label="Closest names" picks={m.candidates.slice(0, 2).map(([g, score]) => ({ label: g, title: `similarity ${score.toFixed(2)}: too close to call, so a person decides`, onPick: () => setNames((n) => ({ ...n, [m.index]: g })) }))} />
              </form>
            ))}
          </div>
        )
      )}

      {user?.key === 'pharmacist' && r.decisions.handed > 0 && (
        <p className="status-line tone-handed"><span className="sq" aria-hidden="true" />{plural(r.decisions.handed, 'alert')} handed over to you. Accept or override each one in the actions below.</p>
      )}

      {may('medication_list') && (
        editing ? (
          <form className="role-list" onSubmit={async (e) => { e.preventDefault(); if (await act('Medication list saved', 'medication_list', { actor, medication_list: list })) setEditing(false); }}>
            <label className="field" style={{ marginTop: 0 }}>
              <span className="label">Medication list, as written</span>
              <textarea className="mono" rows={8} value={list} onChange={(e) => setList(e.target.value)} spellCheck={false} />
            </label>
            <QuickFill label="Add a line" picks={ADD_LINE_EXAMPLES.map((line) => ({ label: `+ ${line}`, onPick: () => setList((l) => `${l.trimEnd()}
${line}`) }))} />
            <div className="handoff-actions">
              <button type="submit" className="btn btn-turn btn-sm">Save and re-run</button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </form>
        ) : <div><button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>Edit the medication list</button></div>
      )}

      {(user?.key === 'prescriber' || user?.key === 'pharmacist') && r.decisions.submitted > 0 && (
        <div><a className="btn btn-secondary btn-sm" href="#actions">Go to the actions ({r.decisions.decided} of {r.decisions.submitted} decided)</a></div>
      )}
      {user?.key === 'reviewer' && <p className="meta">Read-only: the reviewer role makes no entries and no decisions.</p>}

      {next && !mine.length && <SwitchHint role={next.role} text={`Next: ${ROLE[next.role].title}. ${next.text}.`} />}

      <details className="role-history">
        <summary>Record history ({r.history.length + r.events.filter((e) => e.event !== 'shown').length} entries)</summary>
        <ol className="timeline">
          {[...r.history.map((h) => ({ at: h.at, role: h.role, who: h.user, what: `${h.entry.replace('_', ' ')}: ${h.detail}` })),
            ...r.events.filter((e) => e.event !== 'shown').map((e) => ({ at: e.timestamp, role: e.role, who: e.user, what: `${e.event} ${e.alert}${e.reason ? ` (${e.reason})` : ''}${e.note ? `: ${e.note}` : ''}` }))]
            .sort((a, b) => a.at.localeCompare(b.at))
            .map((h, i) => (
              <li key={i}>{h.role in ROLE ? <RoleName role={h.role as RoleKey} /> : <span>{h.role}</span>}<span className="mono ink-3">{when(h.at)}</span><span>{h.who}: {h.what}</span></li>
            ))}
        </ol>
      </details>
    </section>
  );
}

export function WardRecordScreen() {
  const { id = '' } = useParams();
  const up = useWardUp();
  const actor = useActor();
  const toast = useToast();
  const { x } = useData();
  const { rows } = useWard();
  const { record, error, send, setError, reload } = useRecord(id);
  const sent = useRef(new Set<string>());

  // Log that each submitted alert was shown to this clinician, once (medsafe.workflow EVENTS "shown").
  useEffect(() => {
    if (!record || !actor || !['prescriber', 'pharmacist'].includes(actor.role)) return;
    const seen = new Set(record.events.filter((e) => e.event === 'shown' && e.user === actor.user).map((e) => e.alert));
    const unseen = (record.result.medsafe.alerts ?? []).filter((a) => a.submitted && !seen.has(a.key) && !sent.current.has(`${actor.user}:${a.key}`));
    if (unseen.length === 0) return;
    unseen.forEach((a) => sent.current.add(`${actor.user}:${a.key}`));
    Promise.all(unseen.map((a) => api(`records/${id}/events`, { actor, alert: a.key, event: 'shown' })))
      .catch((e: Error) => setError(e.message));
  }, [record, actor, id, setError]);

  // Another window changed this record: read it again.
  const row = rows?.find((r) => r.id === id);
  const signature = row ? JSON.stringify([row.egfr, row.tasks, row.decisions, row.review_requested]) : null;
  const last = useRef(signature);
  useEffect(() => {
    if (signature && last.current && signature !== last.current) reload();
    last.current = signature;
  }, [signature, reload]);

  if (up === false) return <div className="content"><ServerDown /></div>;
  if (!record) return <div className="content">{error ? <p className="empty">{error}</p> : <p className="empty">Reading the record</p>}</div>;

  const d = {
    states: record.alert_states,
    onEvent: async (alert: string, event: AlertEvent, reason?: string, note?: string) => !!(await send('events', { actor, alert, event, reason, note })),
  };
  const trust = {
    requested: record.review_requested, history: record.history,
    onRequest: async (note: string) => {
      const after = await send('review', { actor, note });
      if (after) {
        toast(after.review_requested
          ? { tone: 'handed', title: `${record.id} flagged for pharmacist review`, body: 'It is now on the pharmacist\'s task list.' }
          : { tone: 'done', title: 'Review closed', body: 'The record leaves the pharmacist\'s task list.' });
      }
      return !!after;
    },
  };
  return (
    <PatientScreen p={record.result} ward={{ d, trust }} title={<>Ward record <span className="mono">{record.id}</span></>}
      top={<>
        {error && <p className="form-error" role="alert">{error}</p>}
        <CarePath r={record} />
        <RolePanel key={`${record.id}:${actor?.role}`} r={record} send={send} />
        <p className="meta ward-disclaimer">{x.workflow.disclaimer}</p>
      </>} />
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
            <thead><tr><th>Issue type</th><th className="num">Shown</th><th className="num">Overridden</th><th>Override rate</th><th>Reasons, most common first</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.issue_type}>
                  <th scope="row">{ISSUE_LABEL[r.issue_type] ?? r.issue_type}</th>
                  <td className="num">{r.shown}</td><td className="num">{r.overridden}</td>
                  <td><span className="dec-cell"><Meter value={r.rate} width={96} height={6} color="var(--warn)" /><span className="mono">{pct(r.rate)}</span></span></td>
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

