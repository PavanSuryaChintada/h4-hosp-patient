import type { ReactNode } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import type { PatientView } from '../data/contract';
import { SEVERITY_TONE, plural } from '../data/format';
import { useData } from '../data/load';
import { EhrScreen } from '../components/Ehr';
import { Actions, AlertGraph, type Decisions } from '../components/Medsafe';
import { MedicationPanel } from '../components/Medications';
import { TrustPanel, type WardTrust } from '../components/Trust';
import { NotBuilt, NotBuiltValue, Segmented } from '../components/ui';

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

function Header({ p, mode, setMode }: { p: PatientView; mode: Mode; setMode: (m: Mode) => void }) {
  const sex = p.sex === 'F' ? 'female' : p.sex === 'M' ? 'male' : null;
  return (
    <section className="pt-head" aria-label="Patient">
      <div className="pt-top">
        <h1 className="display">Patient <span className="mono">{p.id}</span></h1>
        <Segmented className="seg-lg" label="Which check to show" value={mode} onChange={setMode} segments={[
          { value: 'ehr', label: 'Standard EHR check' },
          { value: 'medsafe', label: 'Medsafe' },
        ]} />
      </div>
      <div className="pt-facts">
        {p.age !== null && <span><span className="mono">{p.age}</span> y{sex ? `, ${sex}` : ''}</span>}
        {p.weight_kg !== null && <><span className="dot">·</span><span><span className="mono">{p.weight_kg}</span> kg</span></>}
        <span className="dot">·</span><span>{plural(p.medications.length, 'line')} on the list</span>
        {mode === 'medsafe' && p.prescriber_count !== null && <><span className="dot">·</span><span>{plural(p.prescriber_count, 'prescriber')}</span></>}
        {mode === 'medsafe' && p.pregnant !== null && <><span className="dot">·</span><span>{p.pregnant ? 'pregnant' : 'not pregnant'}</span></>}
      </div>
      {mode === 'medsafe' && (
        <div className="pt-context">
          <div className="egfr-big">
            <span className="label">eGFR</span>
            {p.egfr === null
              ? <span className="egfr-none">not recorded</span>
              : <span className="egfr-val mono">{fmtEgfr(p.egfr)}</span>}
            {p.egfr !== null && <Tier p={p} />}
          </div>
          <div className="pt-dx">
            {p.diagnoses.map((d) => <span key={d} className="dx-tag">{d}</span>)}
            {p.allergies && <span className="dx-tag dx-allergy">Allergies: {p.allergies}</span>}
          </div>
        </div>
      )}
    </section>
  );
}

function MedsafeBody({ p, d }: { p: PatientView; d?: Decisions }) {
  const { actions, alerts, collapse } = p.medsafe;
  return (
    <div className="ms-body">
      <section className="panel" aria-label="Prioritised actions">
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

/** One patient, either from the training-set export or a ward record. `ward` adds its decisions and handoffs. */
export function PatientScreen({ p, ward, top }: { p: PatientView; ward?: { d: Decisions; trust: WardTrust }; top?: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const mode: Mode = params.get('mode') === 'ehr' ? 'ehr' : 'medsafe';
  const setMode = (m: Mode) => {
    const next = new URLSearchParams(params);
    if (m === 'ehr') next.set('mode', 'ehr'); else next.delete('mode');
    setParams(next, { replace: true });
  };
  return (
    <div className="content">
      <Header p={p} mode={mode} setMode={setMode} />
      {top}
      <CompareStrip p={p} mode={mode} />
      <div className="pt-body">
        <div className="pt-main">{mode === 'ehr' ? <EhrScreen p={p} /> : <MedsafeBody p={p} d={ward?.d} />}</div>
        <TrustPanel p={p} ward={ward?.trust} />
      </div>
    </div>
  );
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
  return <PatientScreen p={p} />;
}
