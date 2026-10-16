import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CLASS_LABEL, DRUG } from '../data/drugs';
import { BY_ID, name, type Alert } from '../data/engine';
import { AlertGraph } from '../components/AlertGraph';
import { Segmented, StatusCell } from '../components/ui';

type Mode = 'collapsed' | 'all';

const DEFAULT_SEV = { major: 'high', moderate: 'medium', minor: 'low' } as Record<string, string>;

function IssueCell({ a }: { a: Alert }) {
  let re: string | null = null;
  if (a.kind === 'cluster') re = `${a.drugs.length - 1} interactions, 1 drug`;
  else if (a.kind === 'renal') re = `Renal flag, ${a.rescored}`;
  else if (a.rescored && DEFAULT_SEV[a.tableSeverity] !== a.severity) re = `Table ${a.tableSeverity}, re-scored for ${a.rescored}`;
  else if (a.kind === 'interaction') re = `Table ${a.tableSeverity}`;
  return <td className="issue">{a.type}{re && <span className="re">{re}</span>}</td>;
}

function DrugsCell({ a }: { a: Alert }) {
  if (a.kind === 'cluster') {
    return (
      <td className="drugs">
        <span className="anchor">{name(a.drugs[0])}</span>
        <span className="ink-2" style={{ display: 'block' }}>with {a.drugs.slice(1).map(name).join(', ')}</span>
      </td>
    );
  }
  if (a.kind === 'duplicate' && a.drugs[0] === a.drugs[1]) return <td className="drugs">{name(a.drugs[0])} ×2</td>;
  return <td className="drugs">{a.drugs.map(name).join(' + ')}</td>;
}

export function PatientDetail() {
  const { id = '' } = useParams();
  const [mode, setMode] = useState<Mode>('collapsed');
  const x = BY_ID[id];

  if (!x) {
    return (
      <div className="content">
        <h1 className="display">Patient {id}</h1>
        <p className="empty" style={{ marginTop: 16 }}>No patient with this id in the queue. <Link to="/">Back to patients</Link></p>
      </div>
    );
  }

  const p = x.patient;
  const rows = mode === 'collapsed' ? x.collapsed : x.all;
  const lows = x.all.filter((a) => a.severity === 'low').length;
  const anchor = x.anchors[0];
  const aboutAnchor = anchor ? x.all.filter((a) => a.drugs.includes(anchor)).length : 0;
  const counts: Record<string, number> = {};
  for (const m of p.meds) if (m.code) counts[m.code] = (counts[m.code] ?? 0) + 1;

  const fatigue = x.all.length === 0 ? null
    : anchor
      ? `Every pair: ${x.all.length} alerts, ${aboutAnchor} of them about ${name(anchor)}, ${lows} low severity. This is what a prescriber dismisses.`
      : `Every pair: ${x.all.length} alerts, ${lows} of them low severity. This is what a prescriber dismisses.`;

  const caption = x.serious === 0
    ? 'No serious interactions among the medicines that resolved.'
    : anchor
      ? `${x.serious} interactions → 1 change, not ${x.serious} alerts.`
      : `${x.serious} serious interaction${x.serious > 1 ? 's' : ''}. No single drug the rule table allows stopping clears more than one.`;

  return (
    <div className="content">
      <section className="strip" aria-label="Patient summary">
        <h1 className="display">Patient <span className="mono">{p.id}</span></h1>
        <div className="facts">
          <span><span className="mono">{p.age}</span> y</span><span className="dot">·</span>
          <span>{p.sex === 'F' ? 'female' : 'male'}</span><span className="dot">·</span>
          <span><span className="mono">{p.weight}</span> kg</span><span className="dot">·</span>
          <span>eGFR <span className="mono">{p.egfr}</span>{p.egfr < 45 && <span className="tag tag-warn" style={{ marginLeft: 8 }}>low</span>}</span><span className="dot">·</span>
          <span>{p.pregnant ? <span className="tag tag-warn">pregnant</span> : p.sex === 'F' ? 'not pregnant' : 'pregnancy n/a'}</span><span className="dot">·</span>
          <span><span className="mono">{p.meds.length}</span> meds</span>
        </div>
        <div className="dx">{p.dx.join(' · ')}</div>
      </section>

      <section className="panel" aria-label="Alerts">
        <div className="panel-head">
          <h2 className="section">Alerts</h2>
          <Segmented label="Alert view" value={mode} onChange={setMode} segments={[
            { value: 'collapsed', label: `Collapsed (${x.collapsed.length})` },
            { value: 'all', label: `Every pair (${x.all.length})` },
          ]} />
        </div>
        {mode === 'all' && fatigue && <div className="fatigue">{fatigue}</div>}
        {rows.length === 0 ? (
          <div className="empty">
            {mode === 'collapsed' && x.all.length > 0
              ? `No high or medium issue found. ${x.all.length} low-severity note${x.all.length > 1 ? 's' : ''} hidden; see every pair.`
              : 'No issue was found in the medicines that resolved.'}
          </div>
        ) : (
          <table className="t alerts">
            <colgroup>
              <col style={{ width: 104 }} /><col style={{ width: 200 }} /><col style={{ width: 232 }} /><col /><col style={{ width: 96 }} />
            </colgroup>
            <thead>
              <tr><th>Severity</th><th>Issue</th><th>Drugs involved</th><th>Suggested action</th><th className="num">Confidence</th></tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.key} className={a.severity === 'low' ? 'low' : undefined}>
                  <StatusCell level={a.severity} />
                  <IssueCell a={a} />
                  <DrugsCell a={a} />
                  <td className="act">
                    {a.action}
                    {a.note && <span className="note">{a.note}</span>}
                    <span className="src">{a.source}</span>
                  </td>
                  <td className="num">{a.confidence.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="split">
        <section className="panel" aria-label="Alert graph">
          <div className="panel-head"><h2 className="section">Alert graph</h2></div>
          <div className="graph-wrap"><AlertGraph analysis={x} /></div>
          <p className="graph-cap">{caption}</p>
        </section>

        <section className="panel" aria-label="Medicines as written">
          <div className="panel-head">
            <h2 className="section">Medicines as written</h2>
            <span className="meta">As written → resolved generic · confidence</span>
          </div>
          {p.meds.map((m, i) => (
            <div key={i} className={`medrow${m.code ? '' : ' abst'}`}>
              <span className="raw" title={m.raw}>"{m.raw}"</span>
              <span className="arr" aria-hidden="true">→</span>
              {m.code ? (
                <span className="res">
                  {DRUG[m.code].name}
                  <span className="cls">{CLASS_LABEL[DRUG[m.code].cls]}</span>
                  {counts[m.code] > 1 && <span className="dupe">duplicate</span>}
                </span>
              ) : (
                <span className="res">
                  could not resolve
                  <span className="verify">Verify manually. Not checked against the rules.</span>
                  <span className="cand">{m.candidates!.map(([c, s]) => `${c} ${s.toFixed(2)}`).join(' · ')}</span>
                </span>
              )}
              <span className="cf" style={{ color: m.code ? undefined : 'var(--warn)' }}>{m.confidence.toFixed(2)}</span>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
