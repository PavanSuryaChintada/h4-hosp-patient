import { useState } from 'react';
import { Link } from 'react-router-dom';
import { DRUG } from '../data/drugs';
import { METRICS, RESOLUTION_ROWS } from '../data/engine';
import type { Method } from '../data/patients';
import { Segmented } from '../components/ui';
import { Kpi, Meter, StackedBar, Units, repeat } from '../components/viz';

type Filter = 'all' | Method;
const TAG: Record<Method, string> = { exact: 'tag-ok', fuzzy: 'tag-action', abstained: 'tag-warn' };
const METHOD_COLOR: Record<Method, string> = { exact: 'var(--ok)', fuzzy: 'var(--action)', abstained: 'var(--warn)' };

// Confidence histogram, 0.50 to 1.00 in steps of 0.05, stacked by method.
const BINS = Array.from({ length: 10 }, (_, i) => 0.5 + i * 0.05);
const binOf = (c: number) => Math.min(9, Math.max(0, Math.floor((c - 0.5) / 0.05 + 1e-9)));
const hist = BINS.map((_, i) => {
  const inBin = RESOLUTION_ROWS.filter((r) => binOf(r.confidence) === i);
  return { exact: inBin.filter((r) => r.method === 'exact').length, fuzzy: inBin.filter((r) => r.method === 'fuzzy').length, abstained: inBin.filter((r) => r.method === 'abstained').length };
});
const histMax = Math.max(...hist.map((h) => h.exact + h.fuzzy + h.abstained));

function ConfidenceHistogram() {
  const H = 96;
  return (
    <div className="chist" role="img" aria-label="Confidence distribution of every resolved line, by method">
      <div className="chist-bars">
        {hist.map((h, i) => (
          <div key={i} className="chist-col" title={`${BINS[i].toFixed(2)}–${(BINS[i] + 0.05).toFixed(2)}: ${h.exact + h.fuzzy + h.abstained}`}>
            {(['abstained', 'fuzzy', 'exact'] as Method[]).map((m) => h[m] > 0 && (
              <span key={m} style={{ height: (h[m] / histMax) * H, background: METHOD_COLOR[m] }} />
            ))}
          </div>
        ))}
      </div>
      <div className="chist-axis mono"><span>0.50</span><span>0.75</span><span>1.00</span></div>
    </div>
  );
}

export function Resolution() {
  const [filter, setFilter] = useState<Filter>('all');
  const r = METRICS.resolution;
  const pct = Math.round((r.fuzzyCorrect / r.fuzzy) * 100);
  const rows = filter === 'all' ? RESOLUTION_ROWS : RESOLUTION_ROWS.filter((x) => x.method === filter);

  return (
    <div className="content">
      <div className="page-head">
        <h1 className="display">Name resolution</h1>
        <p className="meta">Every medicine string in the cohort, exactly as written on the slip, and what it resolved to.</p>
      </div>

      <div className="kpis kpis-3">
        <div data-tour="resolution-stat">
          <Kpi label="Accuracy on misspelled inputs" value={`${pct}%`}
            sub={<><span className="mono">{r.fuzzyCorrect}</span> of <span className="mono">{r.fuzzy}</span> fuzzy matches agree with the ground-truth labels. Abstentions are not counted as correct.</>}>
            <Units label={`${r.fuzzyCorrect} correct, ${r.fuzzy - r.fuzzyCorrect} wrong`} size={8} gap={2} columns={28}
              items={[...repeat(r.fuzzyCorrect, { color: 'var(--action)' }), ...repeat(r.fuzzy - r.fuzzyCorrect, { color: 'var(--critical)', hollow: true, title: 'Wrong match' })]} />
          </Kpi>
        </div>
        <Kpi label="How each line was matched" value={<>{r.total} <span className="kpi-of">lines</span></>}>
          <StackedBar label="Match method" height={14} segments={[
            { name: 'Exact', value: r.exact, color: METHOD_COLOR.exact },
            { name: 'Fuzzy', value: r.fuzzy, color: METHOD_COLOR.fuzzy },
            { name: 'Abstained', value: r.abstained, color: METHOD_COLOR.abstained },
          ]} />
        </Kpi>
        <Kpi label="Confidence" value={<>{r.abstained} <span className="kpi-of">too close to call</span></>}>
          <ConfidenceHistogram />
        </Kpi>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Segmented label="Filter by method" value={filter} onChange={setFilter} segments={[
          { value: 'all', label: 'All', count: r.total },
          { value: 'exact', label: 'Exact', count: r.exact },
          { value: 'fuzzy', label: 'Fuzzy', count: r.fuzzy },
          { value: 'abstained', label: 'Abstained', count: r.abstained },
        ]} />
      </div>

      <div className="panel">
        <table className="t">
          <colgroup>
            <col style={{ width: 96 }} /><col style={{ width: 240 }} /><col style={{ width: 280 }} />
            <col style={{ width: 152 }} /><col style={{ width: 120 }} /><col />
          </colgroup>
          <thead>
            <tr><th>Patient</th><th>As written</th><th>Resolved</th><th>Confidence</th><th>Method</th><th>Ground truth</th></tr>
          </thead>
          <tbody>
            {rows.map((x, i) => (
              <tr key={i}>
                <td className="mono"><Link to={`/app/patient/${x.patient}`}>{x.patient}</Link></td>
                <td className="mono ink-2">"{x.raw}"</td>
                <td className="mono" style={{ color: x.code ? undefined : 'var(--warn)' }}>
                  {x.code ? DRUG[x.code].name : `could not resolve: ${x.candidates!.map(([c, s]) => `${c} ${s.toFixed(2)}`).join(' / ')}`}
                </td>
                <td>
                  <span className="cell-conf">
                    <Meter value={x.confidence} width={72} color={METHOD_COLOR[x.method]} />
                    <span className="mono">{x.confidence.toFixed(2)}</span>
                  </span>
                </td>
                <td><span className={`tag ${TAG[x.method]}`}>{x.method}</span></td>
                <td>
                  {x.method === 'abstained' ? <span className="ink-3">sent to manual check</span>
                    : x.truth ? <span style={{ color: 'var(--critical)' }}>wrong: was {DRUG[x.truth].name}</span>
                      : <span className="ink-3">matches</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
