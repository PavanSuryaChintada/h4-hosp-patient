import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PIN_LABEL, plural } from '../data/format';
import { useData } from '../data/load';
import { useDemo } from '../components/Shell';
import { NotBuilt, NotBuiltValue, Segmented } from '../components/ui';
import { Kpi } from '../components/viz';
import { fmtEgfr } from './PatientDetail';

type Filter = 'all' | 'verify';
const PAGE = 50;

function Pins() {
  const { x } = useData();
  if (!x.demo) return null;
  return (
    <section className="pins" aria-label="Pinned demo patients">
      {x.demo.pins.map((p) => (
        <div key={p.slot} className="pin">
          <span className="pin-l">{PIN_LABEL[p.slot]}</span>
          <span className="pin-ids">
            {p.patient_ids.length ? p.patient_ids.map((id) => <Link key={id} className="mono" to={`/app/patient/${id}`}>{id}</Link>) : <span className="ink-3">none found</span>}
          </span>
          {p.why && <span className="pin-why">{p.why}</span>}
          <span className="pin-basis">{p.basis === 'labels' ? 'chosen from the training labels' : 'chosen from pipeline output'}</span>
        </div>
      ))}
    </section>
  );
}

export function Queue() {
  const { x } = useData();
  const demo = useDemo();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [shown, setShown] = useState(PAGE);
  const rulesBuilt = x.stages.some((s) => s.id === 'output' && s.built);

  const rows = useMemo(() => {
    const q = query.trim().toUpperCase();
    return x.patients.filter((p) => (filter === 'all' || p.compare.medsafe.to_verify > 0) && (!q || p.id.includes(q)));
  }, [x.patients, filter, query]);

  const r = x.resolution;
  const cohort = x.ehr_reference.cohort;

  return (
    <div className="content">
      <div className="page-head">
        <h1 className="display">Patients</h1>
        <p className="meta">{plural(x.source.patients, 'patient')} from the {x.source.split} split, as the pipeline output them.</p>
      </div>

      {demo && <Pins />}

      <div className="kpis kpis-3">
        <Kpi label="Lines read" value={<>{r.lines} <span className="kpi-of">lines</span></>}
          sub={<>None dropped. <span className="mono">{r.by_method.abstained ?? 0}</span> marked for a manual check, <span className="mono">{r.brand_combinations}</span> combination brands expanded.</>} />
        <Kpi label="Standard EHR check, same patients" value={<>{cohort.alerts_per_patient.toFixed(2)} <span className="kpi-of">alerts per patient</span></>}
          sub={<><span className="mono">{cohort.lines_not_in_formulary}</span> of <span className="mono">{cohort.lines}</span> lines not in its formulary, so never checked.</>} />
        <Kpi label="Medsafe actions" value={rulesBuilt ? <span className="kpi-of">per patient, below</span> : <NotBuiltValue stage="output" />}
          sub={rulesBuilt ? <>Each patient's prioritised actions, from the alert budget.</> : <>Severity order and filters need the rule engine. Until then the queue is in input order.</>} />
      </div>

      {!rulesBuilt && <div style={{ marginBottom: 16 }}><NotBuilt stage="rules" what="Ranking patients by severity needs Medsafe's alerts." /></div>}

      <div className="queue-tools">
        <Segmented label="Filter" value={filter} onChange={(f) => { setFilter(f); setShown(PAGE); }} segments={[
          { value: 'all', label: 'All', count: x.patients.length },
          { value: 'verify', label: 'Has a line to verify', count: r.patients_with_lines_to_verify },
        ]} />
        <label className="search">
          <span className="sr-only">Find a patient by id</span>
          <input type="search" placeholder="Find patient id" value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE); }} />
        </label>
      </div>

      <div className="panel">
        <table className="t queue">
          <colgroup>
            <col style={{ width: 144 }} /><col style={{ width: 80 }} /><col style={{ width: 80 }} /><col style={{ width: 96 }} />
            <col style={{ width: 160 }} /><col style={{ width: 168 }} /><col />
          </colgroup>
          <thead>
            <tr>
              <th>Patient</th><th className="num">Age</th><th className="num">eGFR</th><th className="num">Lines</th>
              <th>Resolved</th><th className="num">Standard EHR alerts</th><th>Medsafe actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, shown).map((p) => {
              const m = p.compare.medsafe;
              const go = () => navigate(`/app/patient/${p.id}`);
              return (
                <tr key={p.id} className="click" tabIndex={0} onClick={go} onKeyDown={(e) => { if (e.key === 'Enter') go(); }} aria-label={`Patient ${p.id}`}>
                  <td className="mono">{p.id}</td>
                  <td className="num">{p.age ?? '—'} <span className="ink-3">{p.sex}</span></td>
                  <td className="num">{p.egfr === null ? <span className="ink-3">—</span> : fmtEgfr(p.egfr)}</td>
                  <td className="num">{m.lines}</td>
                  <td>
                    <span className="mono">{m.checked}/{m.medicines}</span>
                    {m.to_verify > 0 && <span className="tag tag-warn" style={{ marginLeft: 8 }}>{m.to_verify} to verify</span>}
                  </td>
                  <td className="num">{p.compare.ehr.alerts}</td>
                  <td>{m.actions === null ? <NotBuiltValue stage="output" /> : <span className="mono">{m.actions}</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && <p className="empty">No patient matches.</p>}
      </div>
      {rows.length > shown && (
        <div className="more">
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShown((n) => n + PAGE)}>Show {Math.min(PAGE, rows.length - shown)} more</button>
          <span className="meta">Showing <span className="mono">{shown}</span> of <span className="mono">{rows.length}</span></span>
        </div>
      )}
    </div>
  );
}
