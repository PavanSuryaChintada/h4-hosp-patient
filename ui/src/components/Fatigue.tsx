// The alert-fatigue wall: one real patient's standard-check alerts as a wall, against Medsafe's
// actions for the same list. Both come from the export; the switch only changes which is drawn.

import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { PatientView } from '../data/contract';
import { ISSUE_LABEL, SEVERITY_LABEL, SEVERITY_TONE } from '../data/format';
import { Segmented } from './ui';

type Side = 'ehr' | 'medsafe';

export function FatigueWall({ p, seriousLabelled, seriousRaised }: { p: PatientView; seriousLabelled?: number; seriousRaised?: number }) {
  const [side, setSide] = useState<Side>('ehr');
  const alerts = p.medsafe.alerts ?? [];
  const byRank = new Map(alerts.map((a) => [a.rank, a]));
  const actions = p.medsafe.actions ?? [];
  const count = side === 'ehr' ? p.ehr.alerts.length : actions.length;

  return (
    <div className="wall">
      <div className="wall-head">
        <div>
          <span className={`wall-num mono${side === 'medsafe' ? ' good' : ''}`}>{count}</span>
          <span className="wall-what">{side === 'ehr' ? 'alerts from the standard check' : 'actions from Medsafe'}</span>
        </div>
        <Segmented label="Which check" value={side} onChange={setSide} segments={[
          { value: 'ehr', label: 'Standard EHR check', count: p.ehr.alerts.length },
          { value: 'medsafe', label: 'Medsafe', count: actions.length },
        ]} />
      </div>
      <p className="wall-cap">
        {side === 'ehr'
          ? <>Every listed pair at the reference severity, one flat kidney warning per drug, and no view of {p.compare.ehr.not_in_formulary} medicines the formulary does not know.{seriousLabelled !== undefined && <> <span className="mono">{seriousRaised}</span> of the <span className="mono">{seriousLabelled}</span> serious issues on this list are on the wall.</>}</>
          : <>Every line read, combinations opened, the drug to review first at the top{p.medsafe.suppressed ? `, ${p.medsafe.suppressed} minor issues held back` : ''}.</>}
      </p>
      {side === 'ehr' ? (
        <ul className="wall-chips" aria-label="Standard check alerts">
          {p.ehr.alerts.map((a, i) => (
            <li key={i} className="wall-chip" style={{ ['--c' as string]: SEVERITY_TONE[a.severity] }}>
              <span className="sq" aria-hidden="true" /><span className="wall-sev">{SEVERITY_LABEL[a.severity]}</span>
              <span className="wall-text">{ISSUE_LABEL[a.issue_type]}: <span className="mono">{a.drugs.join(' + ')}</span></span>
            </li>
          ))}
        </ul>
      ) : (
        <ol className="wall-actions" aria-label="Medsafe actions">
          {actions.map((act, i) => {
            if (act.kind === 'collapse') {
              return <li key={i} className="wall-action wall-collapse"><strong>{act.summary}</strong><span className="mono">{act.covers.map((r) => byRank.get(r)!.drugs.join(' + ')).join(' · ')}</span></li>;
            }
            const a = byRank.get(act.rank)!;
            return (
              <li key={i} className="wall-action" style={{ ['--c' as string]: SEVERITY_TONE[a.severity] }}>
                <span className="wall-sev">{SEVERITY_LABEL[a.severity]} · {ISSUE_LABEL[a.issue_type]}</span>
                <strong>{a.suggested_action}</strong><span className="mono">{a.drugs.join(' + ')}</span>
              </li>
            );
          })}
        </ol>
      )}
      <Link className="home-case-open" to={`/app/patient/${p.id}${side === 'ehr' ? '?mode=ehr' : ''}`}>Open patient <span className="mono">{p.id}</span> →</Link>
    </div>
  );
}
