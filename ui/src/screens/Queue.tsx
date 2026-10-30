import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { Severity } from '../data/contract';
import { PIN_LABEL, plural } from '../data/format';
import { useData } from '../data/load';
import { useDemo } from '../components/Shell';
import { Bars, SeverityMap, TOP_LABEL, TOP_TONE } from '../components/Charts';
import { Segmented, StatusCell } from '../components/ui';
import { Kpi, Meter, Units, repeat } from '../components/viz';
import { fmtEgfr } from './PatientDetail';

type Filter = 'all' | Severity | 'none' | 'verify';
const PAGE = 50;
const LEVELS: (Severity | 'none')[] = ['contraindicated', 'major', 'moderate', 'none'];

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
  const { x, byId } = useData();
  const demo = useDemo();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [shown, setShown] = useState(PAGE);
  const c = x.cohort;
  const sev = c.by_top_severity ?? {};

  const rows = useMemo(() => {
    const q = query.trim().toUpperCase();
    return c.queue_order.map((id) => byId.get(id)!).filter((p) => {
      const m = p.compare.medsafe;
      const keep = filter === 'all' || (filter === 'verify' ? m.to_verify > 0 : m.top_severity === filter);
      return keep && (!q || p.id.includes(q));
    });
  }, [c.queue_order, byId, filter, query]);

  const t = c.totals;
  return (
    <div className="content">
      <div className="page-head">
        <h1 className="display">Patients</h1>
        <p className="meta">{plural(x.source.patients, 'patient')} from the {x.source.split} split, most urgent first: the most severe alert Medsafe would send, then the number of actions.</p>
      </div>

      {demo && <Pins />}

      <section className="panel map-panel" aria-label="Every patient by severity">
        <div className="panel-head">
          <h2 className="section">Every patient, most urgent first</h2>
          <span className="legend" style={{ marginTop: 0 }}>
            {LEVELS.map((l) => <span key={l}><span className="sw" style={{ background: TOP_TONE[l] }} />{TOP_LABEL[l]} <span className="mono">{sev[l] ?? 0}</span></span>)}
          </span>
        </div>
        <div className="map-body"><SeverityMap order={c.queue_order} byId={byId} /></div>
      </section>

      <div className="kpis kpis-3">
        <Kpi label="Alerts across the cohort" value={<>{t.medsafe_actions.toLocaleString('en-GB')} <span className="kpi-of">Medsafe actions</span></>}
          sub={<>From <span className="mono">{t.medsafe_findings.toLocaleString('en-GB')}</span> findings; <span className="mono">{t.medsafe_submitted.toLocaleString('en-GB')}</span> are serious enough to send. Minor ones are shown last.</>}>
          <div className="kpi-bars">
            {([['Standard check', t.ehr_alerts, 'var(--critical)'], ['Medsafe findings', t.medsafe_findings, 'var(--ink-3)'],
               ['Medsafe sent', t.medsafe_submitted, 'var(--action)'], ['Medsafe actions', t.medsafe_actions, 'var(--ok)']] as const).map(([k, v, col]) => (
              <span key={k} className="kpi-bar-row"><span>{k}</span><Meter value={v} max={Math.max(t.ehr_alerts, t.medsafe_findings)} width={160} height={8} color={col} /><span className="mono">{v.toLocaleString('en-GB')}</span></span>
            ))}
          </div>
        </Kpi>
        <Kpi label="Kidney function (KDIGO category)" value={<>{c.egfr_stages.filter((s) => ['G3a', 'G3b', 'G4', 'G5'].includes(s.code ?? '')).reduce((n, s) => n + s.patients, 0)} <span className="kpi-of">in G3a to G5</span></>}
          sub={<>Display only. The renal alerts use each drug's own tiers from the reference table.</>}>
          <Bars label="Patients by KDIGO eGFR category" items={c.egfr_stages.map((s) => ({ label: s.code ?? 'none', value: s.patients, color: s.code ? 'var(--action)' : 'var(--hairline-firm)', title: `${s.code ?? 'not recorded'}, ${s.label}: ${s.patients}` }))} />
        </Kpi>
        <Kpi label="Lines sent for a manual check" value={<>{t.lines_to_verify} <span className="kpi-of">of {x.resolution.lines.toLocaleString('en-GB')} lines</span></>}
          sub={<>Too close to call, so shown as "verify manually" instead of guessed.</>}>
          <Units label={`${t.lines_to_verify} lines to verify`} size={14} gap={4} items={repeat(Math.min(t.lines_to_verify, 60), { color: 'var(--warn)', hollow: true })} />
        </Kpi>
      </div>

      <div className="queue-tools">
        <Segmented label="Filter by severity" value={filter} onChange={(f) => { setFilter(f); setShown(PAGE); }} segments={[
          { value: 'all', label: 'All', count: x.patients.length },
          ...LEVELS.map((l) => ({ value: l as Filter, label: TOP_LABEL[l], count: sev[l] ?? 0 })),
          { value: 'verify', label: 'Has a line to verify', count: x.resolution.patients_with_lines_to_verify },
        ]} />
        <label className="search">
          <span className="sr-only">Find a patient by id</span>
          <input type="search" placeholder="Find patient id" value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE); }} />
        </label>
      </div>

      <div className="panel">
        <table className="t queue">
          <colgroup>
            <col style={{ width: 144 }} /><col style={{ width: 72 }} /><col style={{ width: 72 }} /><col style={{ width: 150 }} />
            <col style={{ width: 120 }} /><col style={{ width: 120 }} /><col style={{ width: 140 }} /><col />
          </colgroup>
          <thead>
            <tr>
              <th>Patient</th><th className="num">Age</th><th className="num">eGFR</th><th>Severity</th>
              <th className="num">Standard alerts</th><th className="num">Medsafe actions</th><th>Lines resolved</th><th>Review first</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, shown).map((p) => {
              const m = p.compare.medsafe;
              const go = () => navigate(`/app/patient/${p.id}`);
              const top = m.top_severity ?? 'none';
              return (
                <tr key={p.id} className="click" tabIndex={0} onClick={go} onKeyDown={(e) => { if (e.key === 'Enter') go(); }} aria-label={`Patient ${p.id}`}>
                  <td className="mono">{p.id}</td>
                  <td className="num">{p.age ?? '—'} <span className="ink-3">{p.sex}</span></td>
                  <td className="num">{p.egfr === null ? <span className="ink-3">—</span> : fmtEgfr(p.egfr)}</td>
                  {top === 'none' ? <td className="sev" style={{ ['--c' as string]: 'var(--ok)' }}><span className="sq" aria-hidden="true" /><span className="lbl">No issue found</span></td> : <StatusCell severity={top} />}
                  <td className="num">{p.compare.ehr.alerts}</td>
                  <td className="num">{m.actions ?? '—'}</td>
                  <td>
                    <Units label={`${m.checked} of ${m.lines} lines resolved`} size={8} gap={2} columns={Math.min(12, p.medications.length)}
                      items={p.medications.map((md) => ({ color: md.status === 'unresolved' ? 'var(--warn)' : md.status === 'not_a_medicine' || md.status === 'stopped' ? 'var(--hairline-firm)' : 'var(--action)', hollow: md.status === 'unresolved' }))} />
                    {m.to_verify > 0 && <span className="tag tag-warn" style={{ marginLeft: 8 }}>{m.to_verify} to verify</span>}
                  </td>
                  <td className="ink-2 cell-clip">{p.medsafe.collapse?.chosen.length ? `Review ${p.medsafe.collapse.chosen.join(' and ')}` : ''}</td>
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
