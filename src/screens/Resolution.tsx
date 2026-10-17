import { useState } from 'react';
import { Link } from 'react-router-dom';
import { DRUG } from '../data/drugs';
import { METRICS, RESOLUTION_ROWS } from '../data/engine';
import type { Method } from '../data/patients';
import { Segmented, Stat } from '../components/ui';

type Filter = 'all' | Method;
const TAG: Record<Method, string> = { exact: 'tag-ok', fuzzy: 'tag-action', abstained: 'tag-warn' };

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

      <div className="panel" style={{ padding: 24, marginBottom: 24, maxWidth: 720 }} data-tour="resolution-stat">
        <Stat caption="Resolution accuracy on misspelled inputs" figure={`${pct}%`}
          sub={<><span className="mono">{r.fuzzyCorrect}</span> of <span className="mono">{r.fuzzy}</span> fuzzy-matched strings resolved to the right generic, checked against the dataset's ground-truth labels. <span className="mono">{r.abstained}</span> abstained and went to manual check; they are not counted as correct.</>} />
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
            <col style={{ width: 112 }} /><col style={{ width: 120 }} /><col />
          </colgroup>
          <thead>
            <tr><th>Patient</th><th>As written</th><th>Resolved</th><th className="num">Confidence</th><th>Method</th><th>Ground truth</th></tr>
          </thead>
          <tbody>
            {rows.map((x, i) => (
              <tr key={i}>
                <td className="mono"><Link to={`/app/patient/${x.patient}`}>{x.patient}</Link></td>
                <td className="mono ink-2">"{x.raw}"</td>
                <td className="mono" style={{ color: x.code ? undefined : 'var(--warn)' }}>
                  {x.code ? DRUG[x.code].name : `could not resolve: ${x.candidates!.map(([c, s]) => `${c} ${s.toFixed(2)}`).join(' / ')}`}
                </td>
                <td className="num">{x.confidence.toFixed(2)}</td>
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
