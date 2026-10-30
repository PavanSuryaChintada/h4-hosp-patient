// The evaluation report, as eval/run.py wrote it, plus the standard-check reproduction scored by
// the same evaluate.py on the same split. Nothing here is recomputed; numbers are formatted only.

import { useState } from 'react';
import type { Export, OfficialScore } from '../data/contract';
import { ISSUE_LABEL, num } from '../data/format';
import { useData } from '../data/load';
import { PatientLink, Segmented, Stat, StatusInline } from '../components/ui';

function Row({ who, s, note }: { who: string; s: OfficialScore; note?: string }) {
  const c = s.components;
  return (
    <tr>
      <th scope="row">{who}{note && <span className="row-note">{note}</span>}</th>
      <td className="num">{num(s.primary_score, 3)}</td>
      <td className="num">{num(c.serious_recall)}</td>
      <td className="num">{num(c.near_miss_serious_recall)}</td>
      <td className="num">{num(c.precision_all)}</td>
      <td className="num">{num(c.noise_alerts_per_patient)}</td>
      <td className="num">{num(c.resolution_accuracy)}</td>
    </tr>
  );
}

const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

/** python -m eval.ml_challenger: three trained models, each against the rules on holdout. */
function Challengers({ c }: { c: NonNullable<Export['ml_challenger']> }) {
  const n = c.names, d = c.conditions, t = c.triage;
  return (
    <section className="panel" style={{ marginTop: 24 }}>
      <div className="panel-head">
        <h2 className="section">Trained models against the rules</h2>
        <span className="meta">Holdout, <span className="mono">{n.holdout_patients}</span> patients, same rule engine and scorer. <span className="mono">python -m eval.ml_challenger</span></span>
      </div>
      <p className="meta" style={{ padding: '12px 16px 0' }}>
        The submission stays rules only. Each model trains on dev only and is scored once on holdout. Holdout is out of sample for the models only:
        the rules' vocabulary was built on all training text (D-025) and their synonyms on dev failures and general knowledge (D-014), so the rules' perfect rows are optimistic.
      </p>

      <h3 className="ch-h">1 · Reading drug names: n-gram TF-IDF, nearest neighbour</h3>
      <table className="t">
        <thead><tr><th>Name resolution</th><th className="num">Score</th><th className="num">Misspelled lines</th><th className="num">Never seen in dev</th><th className="num">Wrong, not abstained</th><th className="num">Abstained</th></tr></thead>
        <tbody>
          {Object.entries(n.submissions).map(([name, s]) => (
            <tr key={name}>
              <th scope="row">{cap(name)}</th>
              <td className="num">{num(s.primary_score, 3)}</td><td className="num">{num(s.lines.misspelled_accuracy, 3)}</td>
              <td className="num">{num(s.lines.unseen_accuracy, 3)}</td><td className="num">{s.lines.wrong_confident}</td><td className="num">{s.lines.abstained}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="ch-h">2 · Reading conditions and negation: logistic regression</h3>
      <table className="t">
        <thead><tr><th>Condition reader</th><th className="num">Score</th><th className="num">Conditions: precision</th><th className="num">Conditions: recall</th><th className="num">Contraindication recall</th><th className="num">Alerts (matched)</th></tr></thead>
        <tbody>
          {Object.entries(d.official).map(([name, s]) => (
            <tr key={name}>
              <th scope="row">{cap(name)}</th>
              <td className="num">{num(s.primary_score, 3)}</td>
              <td className="num">{num(d.pairs[name].precision)}</td><td className="num">{num(d.pairs[name].recall)}</td>
              <td className="num">{num(s.contraindication.serious_recall)}</td>
              <td className="num">{s.contraindication.alerts} ({s.contraindication.alerts_matched})</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="meta ch-note">Trained on <span className="mono">{d.examples}</span> (patient, condition) pairs labelled from contraindication labels alone, only <span className="mono">{d.present}</span> of them present.</p>

      <h3 className="ch-h">3 · Which alerts are worth showing: gradient-boosted trees</h3>
      <table className="t">
        <thead><tr><th>Submission</th><th className="num">Score</th><th className="num">Noise per patient</th><th className="num">Precision</th><th className="num">Serious recall</th></tr></thead>
        <tbody>
          {Object.entries(t.official).map(([name, s]) => (
            <tr key={name}>
              <th scope="row">{cap(name)}</th>
              <td className="num">{num(s.primary_score, 3)}</td><td className="num">{num(s.components.noise_alerts_per_patient)}</td>
              <td className="num">{num(s.components.precision_all)}</td><td className="num">{num(s.components.serious_recall)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="meta ch-note">
        No outcome data exists here, so the trees learn which standard-check alerts match a real issue that is not minor. On holdout they held back <span className="mono">{t.held_back}</span> of <span className="mono">{t.holdout_alerts}</span> alerts,
        <span className="mono"> {t.held_back_worth_showing}</span> of them worth showing (ranking AUC <span className="mono">{num(t.holdout_auc, 3)}</span>). They split most on {t.importance.slice(0, 3).map(([f]) => f).join(', ')}.
        Triage can only hold back what a check raised; it cannot find what the check never recognised. Report <span className="mono">{c.path}</span>.
      </p>
    </section>
  );
}

export function Evaluation() {
  const { x } = useData();
  const report = x.evaluation.report;
  const names = report ? Object.keys(report.splits) : [];
  const [split, setSplit] = useState(names.includes('holdout') ? 'holdout' : names[0] ?? '');

  if (!report) {
    return (
      <div className="content">
        <div className="page-head"><h1 className="display">Evaluation</h1></div>
        <p className="empty">{x.evaluation.unavailable}</p>
      </div>
    );
  }

  const s = report.splits[split];
  const o = s.official;
  const ehr = x.ehr_reference.score?.split === split ? x.ehr_reference.score.official : undefined;
  const missed = s.near_misses.filter((n) => n.status !== 'caught');

  return (
    <div className="content" style={{ maxWidth: 1200 }}>
      <div className="page-head">
        <h1 className="display">Evaluation</h1>
        <p className="meta">
          Scored by the organisers' <span className="mono">evaluate.py</span>, unmodified. Report <span className="mono">{x.evaluation.path}</span>,
          generated <span className="mono">{report.generated_at}</span> at <span className="mono">{report.git_revision}</span>, data <span className="mono">{report.data_version}</span>.
        </p>
      </div>

      <div className="queue-tools">
        <Segmented label="Split" value={split} onChange={setSplit} segments={names.map((n) => ({ value: n, label: n === 'holdout' ? 'Holdout, never tuned on' : n === 'dev' ? 'Dev, tuned on' : n, count: report.splits[n].patients }))} />
        <span className="meta">Stages built: <span className="mono">{s.stages_built.join(', ')}</span></span>
      </div>

      <div className="eval-stats">
        <div className="panel"><Stat caption="Primary score" figure={num(o.primary_score, 3)} sub="0 to 1, higher is better." /></div>
        <div className="panel"><Stat caption="Serious recall" figure={num(o.components.serious_recall)} sub={<><span className="mono">{o.counts.true_serious}</span> serious issues in the labels.</>} /></div>
        <div className="panel"><Stat caption="Near-miss recall" figure={num(o.components.near_miss_serious_recall)} sub={<><span className="mono">{o.counts.true_near_miss}</span> seeded near-misses.</>} /></div>
        <div className="panel"><Stat caption="Noise per patient" figure={num(o.components.noise_alerts_per_patient)} sub="Two per patient zeroes the score." /></div>
        <div className="panel"><Stat caption="Resolution, misspelled lines" figure={num(o.resolution_accuracy_misspelled, 3)} sub={<>All lines: <span className="mono">{num(o.components.resolution_accuracy, 3)}</span></>} /></div>
      </div>

      {!s.stages_built.includes('rules') && (
        <p className="not-built" style={{ marginTop: 16 }}>
          <span className="nb-head">Read these with the stages built in mind</span>
          <span>The rule engine has not landed, so Medsafe raises no alerts: recall is zero by construction and the score comes from name resolution alone.</span>
        </p>
      )}

      <section className="panel" style={{ marginTop: 24 }}>
        <div className="panel-head"><h2 className="section">Same split, same scorer</h2><span className="meta">Reference submissions from eval/baselines.py</span></div>
        <table className="t">
          <thead>
            <tr><th>Submission</th><th className="num">Score</th><th className="num">Serious recall</th><th className="num">Near-miss recall</th><th className="num">Precision</th><th className="num">Noise per patient</th><th className="num">Resolution</th></tr>
          </thead>
          <tbody>
            <Row who="Medsafe" s={o} />
            {ehr && <Row who="Standard EHR check" note="reproduction, tools/ehr_reference.py" s={ehr} />}
            {Object.entries(s.baselines).map(([name, b]) => <Row key={name} who={name[0].toUpperCase() + name.slice(1)} s={b} />)}
          </tbody>
        </table>
      </section>

      <section className="panel" style={{ marginTop: 24 }}>
        <div className="panel-head"><h2 className="section">Medsafe by issue type</h2></div>
        <table className="t">
          <thead><tr><th>Issue type</th><th className="num">Serious in labels</th><th className="num">Serious recall</th><th className="num">Alerts</th><th className="num">Alerts matched</th></tr></thead>
          <tbody>
            {Object.entries(o.per_issue_type).map(([type, v]) => (
              <tr key={type}>
                <th scope="row">{ISSUE_LABEL[type as keyof typeof ISSUE_LABEL] ?? type}</th>
                <td className="num">{v.serious_true}</td><td className="num">{num(v.serious_recall)}</td>
                <td className="num">{v.alerts}</td><td className="num">{v.alerts_matched}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {x.ml_challenger && <Challengers c={x.ml_challenger} />}

      <h2 className="section" style={{ marginTop: 48, marginBottom: 16 }}>What we missed</h2>
      <div className="panel">
        <table className="t alerts">
          <colgroup><col style={{ width: 144 }} /><col style={{ width: 200 }} /><col style={{ width: 240 }} /><col style={{ width: 280 }} /><col /></colgroup>
          <thead><tr><th>Patient</th><th>Issue</th><th>Drugs</th><th>As written</th><th>Why it was missed</th></tr></thead>
          <tbody>
            {missed.map((n) => (
              <tr key={`${n.patient_id}${n.issue_type}${n.drugs}`}>
                <td><PatientLink id={n.patient_id} /></td>
                <td><StatusInline severity={n.severity} /> <span className="ink-2">{ISSUE_LABEL[n.issue_type]}</span></td>
                <td className="mono">{n.drugs}</td>
                <td className="mono ink-2">{n.as_written}</td>
                <td className="ink-2">{n.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {missed.length === 0 && <p className="empty">Every seeded near-miss on this split was caught.</p>}
      </div>
      <p className="meta" style={{ marginTop: 12 }}><span className="mono">{missed.length}</span> of <span className="mono">{s.near_misses.length}</span> seeded near-misses missed on this split.</p>
    </div>
  );
}
