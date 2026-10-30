// The standard EHR check, as tools/ehr_reference.py reproduced it. Deliberately flat: no motion,
// no grouping, no ranking beyond the reference severity, every box the same weight.

import { useState } from 'react';
import type { EhrAlert, PatientView } from '../data/contract';
import { ISSUE_LABEL, SEVERITY_LABEL, SEVERITY_TONE } from '../data/format';

export function EhrBox({ a, onDismiss }: { a: EhrAlert; onDismiss?: () => void }) {
  return (
    <article className="ehr-box" style={{ ['--c' as string]: SEVERITY_TONE[a.severity] }}>
      <header className="ehr-box-bar">
        <span className="ehr-sev"><span className="sq" aria-hidden="true" />{SEVERITY_LABEL[a.severity]}</span>
        <span className="ehr-kind">{ISSUE_LABEL[a.issue_type]} warning</span>
      </header>
      <div className="ehr-box-body">
        <p className="ehr-drugs mono">{a.drugs.join(' + ')}</p>
        {a.effect && <p>{a.effect}</p>}
        {a.action && <p><span className="ehr-k">Reference advice:</span> {a.action}</p>}
        <p className="ehr-src mono">{a.source}</p>
      </div>
      {onDismiss && (
        <footer className="ehr-box-foot">
          <button type="button" className="ehr-btn" onClick={onDismiss}>Override</button>
          <button type="button" className="ehr-btn" onClick={onDismiss}>Dismiss</button>
        </footer>
      )}
    </article>
  );
}

/** The alert stack with its count and the "Dismiss all" button, as a standard CDS screen shows it. */
export function EhrAlertStack({ alerts, className }: { alerts: EhrAlert[]; className?: string }) {
  const [dismissed, setDismissed] = useState<Set<number>>(() => new Set());
  const open = alerts.map((_, i) => i).filter((i) => !dismissed.has(i));
  const dismiss = (i: number) => setDismissed((d) => new Set(d).add(i));

  return (
    <section className={`ehr-alerts${className ? ` ${className}` : ''}`} aria-label="Standard EHR alerts">
      <div className="ehr-alerts-head">
        <span className="ehr-count"><span className="mono">{alerts.length}</span> {alerts.length === 1 ? 'alert' : 'alerts'}</span>
        {dismissed.size > 0 && <span className="ehr-open"><span className="mono">{open.length}</span> open</span>}
        {open.length > 0 && (
          <button type="button" className="ehr-btn ehr-btn-all" onClick={() => setDismissed(new Set(alerts.map((_, i) => i)))}>Dismiss all</button>
        )}
      </div>
      {alerts.length === 0 && <p className="ehr-quiet">No alerts. The check ran only on the lines it recognised.</p>}
      {alerts.length > 0 && open.length === 0 && (
        <div className="ehr-dismissed">
          <p><span className="mono">{alerts.length}</span> {alerts.length === 1 ? 'alert' : 'alerts'} dismissed, none acted on. On a screen like this, that is the common outcome.</p>
          <button type="button" className="btn-link" onClick={() => setDismissed(new Set())}>Show them again</button>
        </div>
      )}
      {open.map((i) => <EhrBox key={i} a={alerts[i]} onDismiss={() => dismiss(i)} />)}
    </section>
  );
}

/** EHR mode for one patient: the list as entered, unrecognised lines greyed out, and the alert stack. */
export function EhrScreen({ p }: { p: PatientView }) {
  return (
    <div className="ehr">
      <p className="ehr-note">
        A reproduction of a standard hospital drug-safety check, built from the same reference tables: exact formulary
        names only, every listed pair at the reference severity, one flat renal warning per drug.
      </p>
      <div className="ehr-grid">
        <section className="ehr-list" aria-label="Medication list as entered">
          <div className="ehr-list-head">Medication list <span className="ehr-sub">as entered</span></div>
          <table className="ehr-table">
            <thead><tr><th className="num">#</th><th>Entry</th><th>Formulary item</th></tr></thead>
            <tbody>
              {p.medications.map((m) => {
                const hit = p.ehr.matched[m.index];
                return (
                  <tr key={m.index} className={hit ? '' : 'miss'}>
                    <td className="num mono">{m.index + 1}</td>
                    <td className="mono">{m.raw}</td>
                    <td>{hit ?? <span className="ehr-nf">not in formulary, not checked</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="ehr-list-foot">Lines not in formulary are left out of every check on this screen.</p>
        </section>
        <EhrAlertStack alerts={p.ehr.alerts} />
      </div>
    </div>
  );
}
