import { Link, useParams, useSearchParams } from 'react-router-dom';
import { CLASS_LABEL, DRUG } from '../data/drugs';
import { BY_ID, name } from '../data/engine';
import { AlertGraph } from '../components/AlertGraph';
import { AlertCard } from '../components/AlertCard';
import { Segmented } from '../components/ui';
import { EgfrGauge, Icon, Meter, SEV_COLOR, Units, repeat } from '../components/viz';

type Mode = 'collapsed' | 'all';

export function PatientDetail() {
  const { id = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const mode: Mode = params.get('view') === 'all' ? 'all' : 'collapsed';
  const setMode = (m: Mode) => setParams(m === 'all' ? { view: 'all' } : {}, { replace: true });
  const x = BY_ID[id];

  if (!x) {
    return (
      <div className="content">
        <h1 className="display">Patient {id}</h1>
        <p className="empty" style={{ marginTop: 16 }}>No patient with this id in the queue. <Link to="/app">Back to patients</Link></p>
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

  const limits = x.collapsed.length === 0 && x.unresolved === 0
    ? `No issue was found in the ${p.meds.length} medicines listed. This list may be incomplete. A clinician decides.`
    : `Checked ${x.checked} of the ${p.meds.length} medicines listed${x.unresolved ? `; ${x.unresolved} could not be resolved and was not checked` : ''}. Only issues in the rule tables are shown. This list may be incomplete. A clinician decides.`;

  const shownUnits = [
    ...x.collapsed.map((a) => ({ color: SEV_COLOR[a.severity] })),
    ...repeat(x.all.length - x.collapsed.length, { color: 'var(--hairline-firm)', hollow: true }),
  ];

  return (
    <div className="content">
      <section className="pt-head" aria-label="Patient summary" data-tour="strip">
        <div className="pt-title">
          <h1 className="display">Patient <span className="mono">{p.id}</span></h1>
          <div className="pt-dx">{p.dx.map((d) => <span key={d} className="dx-tag">{d}</span>)}</div>
        </div>
        <div className="pt-tiles">
          <div className="pt-tile">
            <div className="pt-k">Age</div>
            <div className="pt-v"><span className="mono">{p.age}</span> <span className="pt-u">y, {p.sex === 'F' ? 'female' : 'male'}</span></div>
          </div>
          <div className="pt-tile">
            <div className="pt-k">Weight</div>
            <div className="pt-v"><span className="mono">{p.weight}</span> <span className="pt-u">kg</span></div>
          </div>
          <div className="pt-tile pt-tile-wide">
            <div className="pt-k">Kidney function {p.egfr < 45 && <span className="tag tag-warn">low</span>}</div>
            <div className="pt-v"><span className="mono" style={{ color: p.egfr < 45 ? 'var(--warn)' : undefined }}>{p.egfr}</span> <span className="pt-u">eGFR</span></div>
            <EgfrGauge value={p.egfr} width={220} height={8} scale />
          </div>
          <div className="pt-tile">
            <div className="pt-k">Pregnancy</div>
            <div className="pt-v pt-v-text">{p.pregnant ? <span className="tag tag-warn">pregnant</span> : p.sex === 'F' ? 'Not pregnant' : 'Not applicable'}</div>
          </div>
          <div className="pt-tile">
            <div className="pt-k">Medicines</div>
            <div className="pt-v"><span className="mono">{p.meds.length}</span> <span className="pt-u">{x.unresolved ? `${x.unresolved} unresolved` : 'all resolved'}</span></div>
            <Units label={`${x.checked} resolved, ${x.unresolved} unresolved`} size={10} gap={3}
              items={p.meds.map((m) => (m.code ? { color: 'var(--action)' } : { color: 'var(--warn)', hollow: true }))} />
          </div>
          <div className="pt-tile">
            <div className="pt-k">Alerts</div>
            <div className="pt-v"><span className="mono">{x.collapsed.length}</span> <span className="pt-u">of {x.all.length} raised</span></div>
            <Units label={`${x.collapsed.length} shown of ${x.all.length}`} size={10} gap={3} items={shownUnits} />
          </div>
        </div>
      </section>

      <section className="panel" aria-label="Alerts" data-tour="alerts">
        <div className="panel-head">
          <h2 className="section">Alerts</h2>
          <div data-tour="alert-toggle"><Segmented label="Alert view" value={mode} onChange={setMode} segments={[
            { value: 'collapsed', label: `Collapsed (${x.collapsed.length})` },
            { value: 'all', label: `Every pair (${x.all.length})` },
          ]} /></div>
        </div>
        {mode === 'all' && fatigue && <div className="fatigue"><Icon name="alert" size={14} />{fatigue}</div>}
        {rows.length === 0 ? (
          <div className="empty empty-ok">
            <Icon name="shield" size={20} />
            {mode === 'collapsed' && x.all.length > 0
              ? `No high or medium issue found. ${x.all.length} low-severity note${x.all.length > 1 ? 's' : ''} hidden; see every pair.`
              : 'No issue was found in the medicines that resolved.'}
          </div>
        ) : (
          <div className={`alert-list${mode === 'all' ? ' alert-grid' : ''}`}>
            {rows.map((a) => <AlertCard key={a.key} a={a} analysis={x} compact={mode === 'all'} />)}
          </div>
        )}
      </section>

      <div className="split">
        <section className="panel" aria-label="Alert graph" data-tour="graph">
          <div className="panel-head">
            <h2 className="section">Alert graph</h2>
            <span className="graph-key"><span className="gk gk-serious" />serious <span className="gk gk-other" />other</span>
          </div>
          <div className="graph-wrap"><AlertGraph analysis={x} /></div>
          <p className="graph-cap">{caption}</p>
        </section>

        <section className="panel" aria-label="Medicines as written" data-tour="meds">
          <div className="panel-head">
            <h2 className="section">Medicines as written</h2>
            <span className="meta">Slip text, resolved generic, confidence</span>
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
              <span className="cf">
                <Meter value={m.confidence} width={48} color={m.code ? 'var(--action)' : 'var(--warn)'} />
                <span className="mono" style={{ color: m.code ? undefined : 'var(--warn)' }}>{m.confidence.toFixed(2)}</span>
              </span>
            </div>
          ))}
        </section>
      </div>

      <footer className="limits" role="note" data-tour="limits"><Icon name="shield" size={16} />{limits}</footer>
    </div>
  );
}
