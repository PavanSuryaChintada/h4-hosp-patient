import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ANALYSES } from '../data/engine';
import { Segmented, StatusCell } from '../components/ui';

type Filter = 'all' | 'high' | 'medium' | 'cleared';
const RANK = { high: 0, medium: 1, low: 2, cleared: 3 };

const sorted = ANALYSES.slice().sort((x, y) =>
  RANK[x.top] - RANK[y.top] || y.all.length - x.all.length || y.collapsed.length - x.collapsed.length || x.patient.id.localeCompare(y.patient.id));

export function Queue() {
  const [filter, setFilter] = useState<Filter>('all');
  const navigate = useNavigate();
  const count = (f: Filter) => (f === 'all' ? ANALYSES.length : ANALYSES.filter((x) => x.top === f).length);
  const rows = filter === 'all' ? sorted : sorted.filter((x) => x.top === filter);

  return (
    <div className="content">
      <div className="page-head">
        <h1 className="display">Patients</h1>
        <p className="meta">{ANALYSES.length} prescriptions awaiting review. Highest severity first.</p>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Segmented label="Filter by severity" value={filter} onChange={setFilter} segments={[
          { value: 'all', label: 'All', count: count('all') },
          { value: 'high', label: 'High', count: count('high') },
          { value: 'medium', label: 'Medium', count: count('medium') },
          { value: 'cleared', label: 'Cleared', count: count('cleared') },
        ]} />
      </div>

      <div className="panel">
        <table className="t">
          <colgroup>
            <col style={{ width: 96 }} /><col style={{ width: 64 }} /><col style={{ width: 72 }} />
            <col style={{ width: 64 }} /><col style={{ width: 120 }} /><col style={{ width: 96 }} /><col />
          </colgroup>
          <thead>
            <tr>
              <th>Patient</th><th className="num">Age</th><th className="num">eGFR</th><th className="num">Meds</th>
              <th>Severity</th><th className="num">Alerts</th><th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => {
              const p = x.patient;
              const go = () => navigate(`/patient/${p.id}`);
              return (
                <tr key={p.id} className="click" tabIndex={0} onClick={go}
                  onKeyDown={(e) => { if (e.key === 'Enter') go(); }} aria-label={`Patient ${p.id}`}>
                  <td className="mono">{p.id}</td>
                  <td className="num">{p.age}</td>
                  <td className="num" style={{ color: p.egfr < 45 ? 'var(--warn)' : undefined }}>{p.egfr}</td>
                  <td className="num">{p.meds.length}</td>
                  <StatusCell level={x.top} />
                  <td className="num">{x.collapsed.length} <span className="ink-3">of {x.all.length}</span></td>
                  <td className="ink-2" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 0 }}>
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
