import { Link } from 'react-router-dom';
import { METRICS } from '../data/engine';
import { NEAR_MISS } from '../data/evaluation';
import { GroupedBars } from '../components/Charts';
import { Stat } from '../components/ui';

const LABEL = { high: 'High', medium: 'Medium', low: 'Low' };

export function Evaluation() {
  const m = METRICS;
  return (
    <div className="content" style={{ maxWidth: 1080 }}>
      <div className="page-head">
        <h1 className="display">Evaluation</h1>
        <p className="meta">Two numbers, reported together. One should fall and the other should hold.</p>
      </div>

      <div className="stats" data-tour="eval-stats">
        <div className="panel">
          <Stat caption="Alerts per patient" color="var(--ok)"
            figure={<>{m.alertsBefore.toFixed(1)}<span className="arrow">→</span>{m.alertsAfter.toFixed(1)}</>}
            sub={<>Down. Mean alerts shown per patient across <span className="mono">{m.patients}</span>, every pair against collapsed and capped.</>} />
        </div>
        <div className="panel">
          <Stat caption="Near-miss recall" color="var(--ink)"
            figure={<>{NEAR_MISS.caught} / {NEAR_MISS.seeded}</>}
            sub={<>Held. Seeded subtle-but-serious issues still flagged after the collapse.</>} />
        </div>
      </div>

      <section className="panel" style={{ marginTop: 24 }}>
        <div className="panel-head">
          <h2 className="section">Alerts raised, by severity</h2>
          <span className="meta">Cohort totals: <span className="mono">{m.totalBefore}</span> every pair, <span className="mono">{m.totalAfter}</span> collapsed</span>
        </div>
        <div style={{ padding: 24 }}>
          <GroupedBars seriesLabels={['every pair', 'collapsed']}
            groups={m.bySeverity.map((s) => ({ label: LABEL[s.sev], a: s.before, b: s.after }))} />
        </div>
      </section>

      <p style={{ marginTop: 24, maxWidth: 680, color: 'var(--ink-2)' }}>
        Cutting alert volume without holding recall is not a win, so both are reported together. Most of the cut is low-severity
        noise and alerts that restate the same drug; high-severity alerts fall only where one change clears several of them.
      </p>

      <h2 className="section" style={{ marginTop: 48, marginBottom: 16 }}>What we missed</h2>
      <div className="panel">
        <table className="t alerts">
          <colgroup><col style={{ width: 96 }} /><col style={{ width: 240 }} /><col style={{ width: 280 }} /><col /></colgroup>
          <thead><tr><th>Patient</th><th>Issue</th><th>Should have been</th><th>Why it was missed</th></tr></thead>
          <tbody>
            {NEAR_MISS.missed.map((x) => (
              <tr key={x.patient}>
                <td className="mono"><Link to={`/app/patient/${x.patient}`}>{x.patient}</Link></td>
                <td style={{ fontWeight: 500 }}>{x.issue}</td>
                <td className="ink-2">{x.expected}</td>
                <td className="ink-2">{x.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="meta" style={{ marginTop: 12 }}>Both misses trace back to name resolution, the step before any rule runs.</p>
    </div>
  );
}
