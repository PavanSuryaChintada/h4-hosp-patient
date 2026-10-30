import { useState, type ReactNode } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth';
import type { PatientView } from '../data/contract';
import { SEVERITY_TONE, plural } from '../data/format';
import { useLocalDecisions } from '../data/decisions';
import { useData } from '../data/load';
import { Modal } from '../components/Modal';
import { EhrScreen } from '../components/Ehr';
import { Actions, AlertGraph, type Decisions } from '../components/Medsafe';
import { MedicationPanel } from '../components/Medications';
import { TrustPanel, type WardTrust } from '../components/Trust';
import { NotBuilt, NotBuiltValue, Segmented } from '../components/ui';
import { EgfrGauge } from '../components/Charts';
import { Units } from '../components/viz';

type Mode = 'ehr' | 'medsafe';

export const fmtEgfr = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

function Tier({ p }: { p: PatientView }) {
  const { x } = useData();
  const tier = p.compare.medsafe.egfr_tier;
  if (tier) {
    return <span className="tier" style={{ color: SEVERITY_TONE[tier.severity] }}>{tier.severity} tier ({tier.generic}, eGFR &lt; {tier.egfr_below})</span>;
  }
  return x.stages.some((s) => s.id === 'rules' && s.built)
    ? <span className="tier ink-3">no renal tier applies</span>
    : <span className="tier">tier: <NotBuiltValue stage="rules" /></span>;
}

/** Always visible in both modes: what each check did with the same list. Every figure is exported. */
function CompareStrip({ p, mode }: { p: PatientView; mode: Mode }) {
  const e = p.compare.ehr, m = p.compare.medsafe;
  return (
    <section className="compare" aria-label="The same list, two checks">
      <div className={`cmp-row${mode === 'ehr' ? ' on' : ''}`}>
        <span className="cmp-k">Standard EHR check</span>
        <span><span className="mono">{e.alerts}</span> {e.alerts === 1 ? 'alert' : 'alerts'}</span>
        <span className="dot">·</span>
        <span><span className="mono">{e.not_in_formulary}</span> {e.not_in_formulary === 1 ? 'medicine' : 'medicines'} not in formulary</span>
        <span className="dot">·</span>
        <span><span className="mono">{e.combinations_unexpanded}</span> {e.combinations_unexpanded === 1 ? 'combination' : 'combinations'} not expanded</span>
        <span className="dot">·</span>
        <span>eGFR not read</span>
      </div>
      <div className={`cmp-row${mode === 'medsafe' ? ' on' : ''}`}>
        <span className="cmp-k">Medsafe</span>
        <span>{m.actions === null ? <>actions <NotBuiltValue stage="output" /></> : <><span className="mono">{m.actions}</span> {m.actions === 1 ? 'action' : 'actions'}</>}</span>
        <span className="dot">·</span>
        <span><span className="mono">{m.dropped}</span> dropped, <span className="mono">{m.to_verify}</span> to verify manually</span>
        <span className="dot">·</span>
        <span><span className="mono">{m.combinations_expanded}</span> {m.combinations_expanded === 1 ? 'combination' : 'combinations'} expanded</span>
        <span className="dot">·</span>
        <span>{m.egfr === null ? 'eGFR not recorded' : <>eGFR <span className="mono">{fmtEgfr(m.egfr)}</span>, <Tier p={p} /></>}</span>
      </div>
    </section>
  );
}

const LINE_TONE: Record<string, { color: string; hollow?: boolean; word: string }> = {
  active: { color: 'var(--action)', word: 'resolved and checked' },
  stopped: { color: 'var(--hairline-firm)', word: 'marked stopped' },
  not_a_medicine: { color: 'var(--hairline-firm)', word: 'not a medicine' },
  unresolved: { color: 'var(--warn)', hollow: true, word: 'verify manually' },
};

/** Summary tiles: who the patient is, kidney function on its scale, the list, and the alerts. */
function Tiles({ p }: { p: PatientView }) {
  const { x } = useData();
  const m = p.compare.medsafe;
  const stage = x.cohort.egfr_stages.find((s) => s.code === m.egfr_stage);
  const alerts = p.medsafe.alerts ?? [];
  return (
    <div className="pt-tiles">
      <div className="pt-tile">
        <div className="pt-k">Age</div>
        <div className="pt-v"><span className="mono">{p.age ?? '—'}</span> <span className="pt-u">y{p.sex ? `, ${p.sex === 'F' ? 'female' : 'male'}` : ''}</span></div>
        <div className="pt-k">{p.pregnant === null ? 'pregnancy not applicable' : p.pregnant ? 'pregnant' : 'not pregnant'}</div>
      </div>
      <div className="pt-tile">
        <div className="pt-k">Weight</div>
        <div className="pt-v">{p.weight_kg === null ? <span className="pt-u">not recorded</span> : <><span className="mono">{p.weight_kg}</span> <span className="pt-u">kg</span></>}</div>
        <div className="pt-k">{plural(p.prescriber_count ?? 0, 'prescriber')}</div>
      </div>
      <div className="pt-tile pt-tile-wide">
        <div className="pt-k">Kidney function {stage?.code && <span className="tag tag-grey">KDIGO {stage.code}, {stage.label}</span>}</div>
        {p.egfr === null
          ? <div className="pt-v"><span className="pt-u">eGFR not recorded</span></div>
          : <>
              <div className="pt-v"><span className="mono">{fmtEgfr(p.egfr)}</span> <span className="pt-u">eGFR</span> <Tier p={p} /></div>
              <EgfrGauge value={p.egfr} stages={x.cohort.egfr_stages} />
            </>}
      </div>
      <div className="pt-tile">
        <div className="pt-k">Medicines</div>
        <div className="pt-v"><span className="mono">{m.checked}</span> <span className="pt-u">of {m.lines} resolved</span></div>
        <Units label={p.medications.map((md) => `"${md.raw}": ${LINE_TONE[md.status ?? 'active'].word}`).join('; ')} size={10} gap={3}
          items={p.medications.map((md) => ({ ...LINE_TONE[md.status ?? 'active'], title: `"${md.raw}": ${LINE_TONE[md.status ?? 'active'].word}` }))} />
      </div>
      <div className="pt-tile">
        <div className="pt-k">Alerts</div>
        <div className="pt-v"><span className="mono">{m.actions ?? '—'}</span> <span className="pt-u">actions of {alerts.length} found</span></div>
        <Units label={`${m.actions ?? 0} actions from ${alerts.length} findings`} size={10} gap={3}
          items={alerts.map((a) => ({ color: SEVERITY_TONE[a.severity], hollow: !a.submitted, title: `${a.severity} ${a.issue_type}: ${a.drugs.join(' + ')}${a.submitted ? '' : ' (minor, shown last)'}` }))} />
      </div>
    </div>
  );
}

function Header({ p, mode, setMode, title }: { p: PatientView; mode: Mode; setMode: (m: Mode) => void; title?: ReactNode }) {
  const sex = p.sex === 'F' ? 'female' : p.sex === 'M' ? 'male' : null;
  return (
    <section className="pt-head" aria-label="Patient">
      <div className="pt-top">
        <h1 className="display">{title ?? <>Patient <span className="mono">{p.id}</span></>}</h1>
        <Segmented className="seg-lg" label="Which check to show" value={mode} onChange={setMode} segments={[
          { value: 'ehr', label: 'Standard EHR check' },
          { value: 'medsafe', label: 'Medsafe' },
        ]} />
      </div>
      {mode === 'ehr' && (
        <div className="pt-facts">
          {p.age !== null && <span><span className="mono">{p.age}</span> y{sex ? `, ${sex}` : ''}</span>}
          {p.weight_kg !== null && <><span className="dot">·</span><span><span className="mono">{p.weight_kg}</span> kg</span></>}
          <span className="dot">·</span><span>{plural(p.medications.length, 'line')} on the list</span>
        </div>
      )}
      {mode === 'medsafe' && <Tiles p={p} />}
      {mode === 'medsafe' && (
        <div className="pt-dx" style={{ marginTop: 12 }}>
          {p.diagnoses.map((d) => <span key={d} className="dx-tag">{d}</span>)}
          {p.allergies && <span className="dx-tag dx-allergy">Allergies: {p.allergies}</span>}
        </div>
      )}
    </section>
  );
}

function MedsafeBody({ p, d }: { p: PatientView; d?: Decisions }) {
  const { actions, alerts, collapse } = p.medsafe;
  return (
    <div className="ms-body">
      <section id="actions" className="panel" aria-label="Prioritised actions">
        <div className="panel-head">
          <h2 className="section">Prioritised actions</h2>
          {actions && alerts && <span className="meta"><span className="mono">{actions.length}</span> {actions.length === 1 ? 'action' : 'actions'} from <span className="mono">{alerts.length}</span> {alerts.length === 1 ? 'finding' : 'findings'}</span>}
        </div>
        <Actions p={p} d={d} />
      </section>

      <section className="panel" aria-label="Medicines as written">
        <div className="panel-head">
          <h2 className="section">Medicines as written</h2>
          <span className="meta">Every line kept: resolved, expanded, or marked for a manual check</span>
        </div>
        <MedicationPanel meds={p.medications} />
      </section>

      <section className="panel" aria-label="Alert graph">
        <div className="panel-head"><h2 className="section">Alert graph</h2>{collapse?.summary && <span className="meta">{collapse.summary}</span>}</div>
        {collapse === null
          ? <NotBuilt stage="collapse" what="The graph draws drugs as nodes and interactions as edges, and the drugs to review first." />
          : collapse.edges.length === 0
            ? <p className="empty">No interactions among the medicines on this list.</p>
            : <div className="graph-wrap"><AlertGraph c={collapse} /></div>}
      </section>
    </div>
  );
}

/**
 * The one alert that interrupts: contraindicated combinations nobody has decided on yet, shown to
 * a prescriber once per patient per session. Everything else waits in the prioritised list.
 */
function HardStop({ p, d }: { p: PatientView; d?: Decisions }) {
  const { user } = useAuth();
  const key = `medsafe.hardstop.${p.id}`;
  const open = (p.medsafe.alerts ?? []).filter((a) => a.submitted && a.severity === 'contraindicated' && !d?.states[a.key]);
  const [shown, setShown] = useState(() => {
    try { return user?.key === 'prescriber' && open.length > 0 && !sessionStorage.getItem(key); } catch { return false; }
  });
  if (!shown) return null;
  const close = () => { try { sessionStorage.setItem(key, '1'); } catch { /* storage unavailable */ } setShown(false); };
  const review = () => { close(); document.getElementById('actions')?.scrollIntoView({ block: 'start' }); };
  const collapse = p.medsafe.actions?.find((a) => a.kind === 'collapse');
  return (
    <Modal tone="danger" kicker="Hard stop" title={`${plural(open.length, 'contraindicated combination')} on this list`} onClose={close}
      footer={<><button type="button" className="btn btn-danger" onClick={review}>Review the actions</button><button type="button" className="btn btn-secondary" onClick={close}>Remind me later</button></>}>
      {collapse && collapse.kind === 'collapse' && <p className="modal-quote">{collapse.summary}</p>}
      <ul className="hardstop-list">
        {open.map((a) => (
          <li key={a.key} className="status-line tone-danger"><span className="sq" aria-hidden="true" /><span><strong className="mono">{a.drugs.join(' + ')}</strong> {a.suggested_action}</span></li>
        ))}
      </ul>
      <p className="meta" style={{ marginTop: 12 }}>This is the only alert that interrupts. Everything else waits in the prioritised list, most serious first.</p>
    </Modal>
  );
}

function ModeBanner({ mode, d }: { mode: Mode; d?: Decisions }) {
  return mode === 'ehr'
    ? <p className="mode-banner mode-ehr"><strong>Standard EHR check, reproduced.</strong> Every pair at the table's severity, eGFR not read, names outside the formulary skipped. Flip to Medsafe to compare the same list.</p>
    : <p className="mode-banner mode-ms"><strong>Medsafe.</strong> The most serious first, one drug to review per cluster, every alert with its reasons.{d ? ' Decide on each action below.' : ''}</p>;
}

/** One patient, either from the training-set export or a ward record. `ward` adds its decisions and handoffs. */
export function PatientScreen({ p, ward, top, title, decisions }: {
  p: PatientView; ward?: { d: Decisions; trust: WardTrust }; top?: ReactNode; title?: ReactNode; decisions?: Decisions;
}) {
  const [params, setParams] = useSearchParams();
  const mode: Mode = params.get('mode') === 'ehr' ? 'ehr' : 'medsafe';
  const setMode = (m: Mode) => {
    const next = new URLSearchParams(params);
    if (m === 'ehr') next.set('mode', 'ehr'); else next.delete('mode');
    setParams(next, { replace: true });
  };
  const d = ward?.d ?? decisions;
  return (
    <div className="content">
      <Header p={p} mode={mode} setMode={setMode} title={title} />
      {top}
      <ModeBanner mode={mode} d={d} />
      <CompareStrip p={p} mode={mode} />
      <div className="pt-body">
        <div className="pt-main">{mode === 'ehr' ? <EhrScreen p={p} /> : <MedsafeBody p={p} d={d} />}</div>
        <TrustPanel p={p} ward={ward?.trust} />
      </div>
      {mode === 'medsafe' && <HardStop key={p.id} p={p} d={d} />}
    </div>
  );
}

function TrainingPatient({ p }: { p: PatientView }) {
  const { user } = useAuth();
  const decisions = useLocalDecisions(p.id, user);
  return <PatientScreen p={p} decisions={decisions} />;
}

export function PatientDetail() {
  const { id = '' } = useParams();
  const { byId } = useData();
  const p = byId.get(id);
  if (!p) {
    return (
      <div className="content">
        <h1 className="display">Patient <span className="mono">{id}</span></h1>
        <p className="empty" style={{ marginTop: 16 }}>No patient with this id in the pipeline output. <Link to="/app">Back to patients</Link></p>
      </div>
    );
  }
  return <TrainingPatient p={p} />;
}
