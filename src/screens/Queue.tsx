import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ANALYSES, METRICS } from '../data/engine';
import { HERO_ID } from '../data/patients';
import { Segmented, StatusCell } from '../components/ui';
import { EgfrGauge, Kpi, Meter, SEV_COLOR, Units, repeat } from '../components/viz';

type Filter = 'all' | 'high' | 'medium' | 'cleared';
const RANK = { high: 0, medium: 1, low: 2, cleared: 3 };
const LABEL = { high: 'High', medium: 'Medium', low: 'Low', cleared: 'Cleared' };

const sorted = ANALYSES.slice().sort((x, y) =>
  RANK[x.top] - RANK[y.top] || y.all.length - x.all.length || y.collapsed.length - x.collapsed.length || x.patient.id.localeCompare(y.patient.id));

const count = (f: Filter) => (f === 'all' ? ANALYSES.length : ANALYSES.filter((x) => x.top === f).length);
const BUCKETS: [string, number, number, string][] = [
  ['<30', 0, 30, 'var(--critical)'], ['30–44', 30, 45, 'var(--warn)'], ['45–59', 45, 60, 'var(--ok)'], ['60–89', 60, 90, 'var(--ok)'], ['90+', 90, 999, 'var(--ok)'],
];
const egfrCounts = BUCKETS.map(([, lo, hi]) => ANALYSES.filter((x) => x.patient.egfr >= lo && x.patient.egfr < hi).length);
const lowKidney = ANALYSES.filter((x) => x.patient.egfr < 45).length;
const unresolved = ANALYSES.reduce((s, x) => s + x.unresolved, 0);

export function Queue() {
  const [filter, setFilter] = useState<Filter>('all');
  const navigate = useNavigate();
  const rows = filter === 'all' ? sorted : sorted.filter((x) => x.top === filter);
  const open = (id: string) => navigate(`/app/patient/${id}`);

  return (
    <div className="content">
      <div className="page-head">
        <h1 className="display">Patients</h1>
        <p className="meta">{ANALYSES.length} prescriptions awaiting review. Highest severity first.</p>
      </div>

      <div className="kpis">
        <Kpi label="Needing a change before the prescription leaves" value={<>{count('high')} <span className="kpi-of">high</span></>}
          sub={<span className="legend">{(['high', 'medium', 'cleared'] as const).map((s) => <span key={s}><span className="sw" style={{ background: SEV_COLOR[s] }} />{LABEL[s]} <span className="mono">{count(s)}</span></span>)}</span>}>
          <div className="waffle" aria-label="Every patient, by highest severity. Select one to open it.">
            {sorted.map((x) => (
              <button key={x.patient.id} type="button" className="waffle-cell" style={{ background: SEV_COLOR[x.top] }}
                title={`Patient ${x.patient.id}: ${LABEL[x.top]}`} aria-label={`Open patient ${x.patient.id}, ${LABEL[x.top]}`} onClick={() => open(x.patient.id)} />
            ))}
          </div>
        </Kpi>
        <Kpi label="Alerts shown after the collapse" value={<>{METRICS.totalAfter} <span className="kpi-of">of {METRICS.totalBefore} raised</span></>}
          sub={<>Low-severity notes and repeats stay one click away.</>}>
          <div className="kpi-bars">
            <span>Raised</span><Meter value={METRICS.totalBefore} max={METRICS.totalBefore} width={180} height={8} color="var(--ink-3)" /><span className="mono">{METRICS.totalBefore}</span>
            <span>Shown</span><Meter value={METRICS.totalAfter} max={METRICS.totalBefore} width={180} height={8} color="var(--action)" /><span className="mono">{METRICS.totalAfter}</span>
          </div>
        </Kpi>
        <Kpi label="Low kidney function (eGFR under 45)" value={<>{lowKidney} <span className="kpi-of">patients</span></>} sub={<>Renal rules escalate severity for these patients.</>}>
          <div className="hist" role="img" aria-label={`eGFR distribution: ${BUCKETS.map(([l], i) => `${l}: ${egfrCounts[i]}`).join(', ')}`}>
            {BUCKETS.map(([l, , , c], i) => (
              <div key={l} className="hist-col">
                <span className="hist-n mono">{egfrCounts[i]}</span>
                <span className="hist-bar" style={{ height: `${(egfrCounts[i] / Math.max(...egfrCounts)) * 40}px`, background: c }} />
                <span className="hist-l mono">{l}</span>
              </div>
            ))}
          </div>
        </Kpi>
        <Kpi label="Names sent for a manual check" value={<>{unresolved} <span className="kpi-of">of {METRICS.resolution.total} lines</span></>} sub={<>Too close to call, so excluded from the rules instead of guessed.</>}>
          <Units label={`${unresolved} unresolved`} size={14} gap={4} items={repeat(unresolved, { color: 'var(--warn)', hollow: true })} />
        </Kpi>
      </div>

      <div style={{ marginBottom: 16 }} data-tour="queue-filter">
        <Segmented label="Filter by severity" value={filter} onChange={setFilter} segments={[
          { value: 'all', label: 'All', count: count('all') },
          { value: 'high', label: 'High', count: count('high') },
          { value: 'medium', label: 'Medium', count: count('medium') },
          { value: 'cleared', label: 'Cleared', count: count('cleared') },
        ]} />
      </div>

      <div className="panel">
        <table className="t queue">
          <colgroup>
            <col style={{ width: 96 }} /><col style={{ width: 72 }} /><col style={{ width: 168 }} />
            <col style={{ width: 136 }} /><col style={{ width: 120 }} /><col style={{ width: 176 }} /><col />
          </colgroup>
          <thead>
            <tr>
              <th>Patient</th><th className="num">Age</th><th>Kidney function</th><th>Medicines</th>
              <th>Severity</th><th>Alerts shown</th><th>Top action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => {
              const p = x.patient;
              const go = () => open(p.id);
              return (
                <tr key={p.id} className="click" tabIndex={0} onClick={go} data-tour={p.id === HERO_ID ? 'hero-row' : undefined}
                  onKeyDown={(e) => { if (e.key === 'Enter') go(); }} aria-label={`Patient ${p.id}`}>
                  <td className="mono">{p.id}</td>
                  <td className="num">{p.age} <span className="ink-3">{p.sex}</span></td>
                  <td>
                    <span className="cell-egfr">
                      <EgfrGauge value={p.egfr} width={88} />
                      <span className="mono" style={{ color: p.egfr < 45 ? 'var(--warn)' : undefined }}>{p.egfr}</span>
                    </span>
                  </td>
                  <td>
                    <Units label={`${p.meds.length} medicines${x.unresolved ? `, ${x.unresolved} unresolved` : ''}`} size={8} gap={2}
                      items={p.meds.map((m) => (m.code ? { color: 'var(--action)' } : { color: 'var(--warn)', hollow: true, title: `"${m.raw}" unresolved` }))} />
                    <span className="mono cell-n">{p.meds.length}</span>
                  </td>
                  <StatusCell level={x.top} />
                  <td>
                    <Units label={`${x.collapsed.length} shown of ${x.all.length}`} size={8} gap={2}
                      items={[...x.collapsed.map((a) => ({ color: SEV_COLOR[a.severity] })), ...repeat(x.all.length - x.collapsed.length, { color: 'var(--hairline-firm)', hollow: true })]} />
                    <span className="mono cell-n">{x.collapsed.length}<span className="ink-3">/{x.all.length}</span></span>
                  </td>
                  <td className="ink-2 cell-summary">
                    {x.summary}
                    {x.unresolved > 0 && x.collapsed.length > 0 && <span className="tag tag-warn" style={{ marginLeft: 8 }}>{x.unresolved} unresolved</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
