// Four ways a standard check fails, each on one real training patient chosen by the criteria in
// tools/export_ui.py. The labels choose the patient; everything shown is pipeline or
// standard-check output. Where Medsafe's stage is not built, the card says so.

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { Cards, Label, OfficialScore, PatientView } from '../data/contract';
import { ISSUE_LABEL, SEVERITY_LABEL, num, plural } from '../data/format';
import { useData } from '../data/load';
import { EhrAlertStack, EhrBox } from '../components/Ehr';
import { Actions, MedsafeAlertCard } from '../components/Medsafe';
import { MedRow } from '../components/Medications';
import { TierLadder } from '../components/TierLadder';
import { NotBuilt, StatusInline } from '../components/ui';
import { fmtEgfr } from './PatientDetail';

function Card({ n, title, patients, caption, children, label }: {
  n: number; title: string; patients: string[]; caption: ReactNode; children: ReactNode; label?: Label;
}) {
  return (
    <article className="why-card" aria-labelledby={`why-${n}`}>
      <header className="why-head">
        <span className="why-n mono">{n}</span>
        <h2 id={`why-${n}`} className="section">{title}</h2>
        <span className="why-open">
          {patients.map((id) => <Link key={id} to={`/app/patient/${id}?mode=ehr`}>Open <span className="mono">{id}</span> →</Link>)}
        </span>
      </header>
      <p className="why-cap">{caption}</p>
      {children}
      {label && <AnswerKey label={label} />}
    </article>
  );
}

function AnswerKey({ label }: { label: Label }) {
  return (
    <p className="why-key">
      Answer key, from the training labels: {ISSUE_LABEL[label.issue_type].toLowerCase()}, <span className="mono">{label.drugs.join(' + ')}</span>, <StatusInline severity={label.severity} />
      {label.near_miss && <span className="tag tag-grey" style={{ marginLeft: 8 }}>seeded near-miss</span>}
    </p>
  );
}

function Cols({ ehr, medsafe }: { ehr: ReactNode; medsafe: ReactNode }) {
  return (
    <div className="why-cols">
      <section className="why-col why-ehr"><h3 className="why-col-h">Standard EHR check</h3>{ehr}</section>
      <section className="why-col why-us"><h3 className="why-col-h">Medsafe</h3>{medsafe}</section>
    </div>
  );
}

function EhrLines({ p, lines }: { p: PatientView; lines: number[] }) {
  return (
    <table className="ehr-table why-lines">
      <tbody>
        {lines.map((i) => (
          <tr key={i} className={p.ehr.matched[i] ? '' : 'miss'}>
            <td className="mono">{p.medications[i].raw}</td>
            <td>{p.ehr.matched[i] ?? <span className="ehr-nf">not in formulary</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The standard check's verdict on a card's labelled issue: the alert it raised, or that it raised none. */
function EhrVerdict({ p, index, none }: { p: PatientView; index: number | null; none: string }) {
  return index === null ? <p className="why-verdict miss">{none}</p> : <EhrBox a={p.ehr.alerts[index]} />;
}

/** Medsafe's verdict on the same issue, from pipeline output only. */
function MedsafeVerdict({ p, index, what }: { p: PatientView; index: number | null; what: string }) {
  if (p.medsafe.alerts === null) return <NotBuilt stage="rules" what={`The ${what} alert comes from the rule engine.`} />;
  if (index === null) return <p className="why-verdict miss">Not raised.</p>;
  return <MedsafeAlertCard a={p.medsafe.alerts[index]} />;
}

function BrandChaos({ card }: { card: NonNullable<Cards['brand_chaos']> }) {
  const { byId } = useData();
  const p = byId.get(card.patient_id)!;
  return (
    <Card n={1} title="Brand chaos" patients={[p.id]} label={card.label}
      caption={<>A doctor at a district hospital sees {card.lines.length === 2 ? 'two' : card.lines.length} different words for the same medicine. Here, {card.lines.length === 2 ? 'both are' : 'all of them are'} <span className="mono">{card.generic}</span>.</>}>
      <Cols
        ehr={<><EhrLines p={p} lines={card.lines} /><EhrVerdict p={p} index={card.ehr_alert} none="No duplicate raised: it cannot see that these lines are one medicine." /></>}
        medsafe={<><div className="medlist">{card.lines.map((i) => <MedRow key={i} m={p.medications[i]} />)}</div>
          <MedsafeVerdict p={p} index={card.medsafe_alert} what="duplicate therapy" /></>} />
    </Card>
  );
}

function HiddenGeneric({ card }: { card: NonNullable<Cards['hidden_generic']> }) {
  const { byId } = useData();
  const p = byId.get(card.patient_id)!;
  const lines = [...card.combination_lines, ...card.other_lines].sort((a, b) => a - b);
  return (
    <Card n={2} title="The hidden generic" patients={[p.id]} label={card.label}
      caption={<>Combination brands hide extra generics. This is how a double dose reaches a patient: <span className="mono">{card.generic}</span> is inside one product and also on its own line.</>}>
      <Cols
        ehr={<><EhrLines p={p} lines={lines} /><EhrVerdict p={p} index={card.ehr_alert} none="No duplicate raised: the combination is one product it does not open." /></>}
        medsafe={<><div className="medlist">{lines.map((i) => <MedRow key={i} m={p.medications[i]} highlight={card.combination_lines.includes(i)} />)}</div>
          <MedsafeVerdict p={p} index={card.medsafe_alert} what="duplicate therapy" /></>} />
    </Card>
  );
}

function EgfrBlindness({ card }: { card: NonNullable<Cards['egfr_pair']> }) {
  const { byId } = useData();
  const sides = [card.low, card.high].map((s) => ({ s, p: byId.get(s.patient_id)! }));
  return (
    <Card n={3} title="eGFR blindness" patients={sides.map(({ p }) => p.id)} label={card.label}
      caption={<>The renal rules are tiered by kidney function: the most restrictive tier that applies sets the severity. A check that does not read eGFR fires one flat warning for everyone.</>}>
      <div className="why-ladder">
        <TierLadder generic={card.generic} ladder={card.ladder}
          marks={sides.map(({ s, p }) => ({ label: p.id, egfr: s.egfr }))} />
      </div>
      <div className="why-pair">
        {sides.map(({ s, p }) => (
          <div key={p.id} className="why-pair-col">
            <p className="why-pair-head"><span className="mono">{p.id}</span> · eGFR <span className="mono">{fmtEgfr(s.egfr)}</span></p>
            <div className="medlist"><MedRow m={p.medications[s.line]} /></div>
          </div>
        ))}
        <h3 className="why-row-h">Standard EHR check</h3>
        {sides.map(({ s, p }) => (
          <div key={p.id} className="why-pair-col"><EhrVerdict p={p} index={s.ehr_alert} none="No renal warning." /></div>
        ))}
        <h3 className="why-row-h">Medsafe</h3>
        {sides.map(({ s, p }) => (
          <div key={p.id} className="why-pair-col"><MedsafeVerdict p={p} index={s.medsafe_alert} what="renal dose" /></div>
        ))}
      </div>
    </Card>
  );
}

function ScoreLine({ who, score }: { who: ReactNode; score: OfficialScore }) {
  return (
    <tr>
      <th scope="row">{who}</th>
      <td className="num">{score.counts.alerts_scored} on {score.counts.patients_scored}</td>
      <td className="num">{num(score.components.noise_alerts_per_patient)}</td>
      <td className="num">{num(score.components.serious_recall)}</td>
      <td className="num">{num(score.primary_score, 3)}</td>
    </tr>
  );
}

function AlertFatigue({ card }: { card: NonNullable<Cards['alert_fatigue']> }) {
  const { x, byId } = useData();
  const p = byId.get(card.patient_id)!;
  const ehrScore = x.ehr_reference.score;
  const report = x.evaluation.report;
  const ours = report && ehrScore ? report.splits[ehrScore.split] : undefined;
  return (
    <Card n={4} title="Alert fatigue" patients={[p.id]}
      caption={<>Studies of hospital order-entry systems report clinicians overriding 49% to 96% of drug-safety alerts (van der Sijs et al., JAMIA 2006). In that noise the serious one is lost. Alert fatigue is scored in this challenge for exactly that reason.</>}>
      <Cols
        ehr={<div className="why-overflow"><EhrAlertStack alerts={p.ehr.alerts} /></div>}
        medsafe={<div className="why-overflow why-us-box"><Actions p={p} /></div>} />

      <div className="why-missed">
        <p>
          On this patient the standard check raised <span className="mono">{card.ehr_alerts}</span> alerts.
          The training labels list <span className="mono">{card.serious_labelled}</span> serious issues; <span className="mono">{card.serious_raised}</span> of
          them {card.serious_raised === 1 ? 'is' : 'are'} among those alerts. Not raised:
        </p>
        <ul>
          {card.missed.map((l) => (
            <li key={`${l.issue_type}${l.drugs.join()}`}><StatusInline severity={l.severity} /> {ISSUE_LABEL[l.issue_type]}, <span className="mono">{l.drugs.join(' + ')}</span></li>
          ))}
        </ul>
      </div>

      <h3 className="why-sub">Measured on the {ehrScore?.split ?? 'holdout'} split by the organisers' evaluate.py</h3>
      <table className="t why-scores">
        <thead>
          <tr><th>Check</th><th className="num">Alerts on patients</th><th className="num">Noise per patient</th><th className="num">Serious recall</th><th className="num">Score</th></tr>
        </thead>
        <tbody>
          {ehrScore?.official
            ? <ScoreLine who="Standard EHR check (reproduction)" score={ehrScore.official} />
            : <tr><th scope="row">Standard EHR check</th><td colSpan={4} className="ink-3">{ehrScore?.unavailable ?? 'not scored in this export'}</td></tr>}
          {ours
            ? <ScoreLine who={<>Medsafe <span className="ink-3">(stages built: {ours.stages_built.join(', ')})</span></>} score={ours.official} />
            : <tr><th scope="row">Medsafe</th><td colSpan={4} className="ink-3">{x.evaluation.unavailable ?? 'no report for this split'}</td></tr>}
        </tbody>
      </table>
      <p className="meta" style={{ marginTop: 8 }}>
        On this patient: <span className="mono">{p.compare.ehr.alerts}</span> standard alerts; Medsafe asks for <span className="mono">{p.compare.medsafe.actions ?? '—'}</span> actions
        from <span className="mono">{p.medsafe.alerts?.length ?? '—'}</span> findings, every one of them a labelled issue or a minor one shown last.
        {ours && !ours.stages_built.includes('rules') && ' Medsafe raises no alerts until the rule engine lands, so its recall is zero by construction, not by measurement of a detector.'}
        {x.evaluation.path && <> Medsafe figures from <span className="mono">{x.evaluation.path}</span>.</>}
      </p>
    </Card>
  );
}

export function Why() {
  const { x } = useData();
  const c = x.demo?.cards;
  return (
    <div className="content why">
      <div className="page-head">
        <h1 className="display">Why it matters</h1>
        <p className="meta">
          Four ways a standard check fails, each on one patient from the training set. The standard check is a reproduction
          built from the same reference tables (exact names, every listed pair, a flat renal warning), not a vendor product.
        </p>
      </div>
      {!c ? <p className="empty">The cards are built from the training split. This export is the {x.source.split} split.</p> : (
        <>
          {c.brand_chaos ? <BrandChaos card={c.brand_chaos} /> : <p className="empty">No brand-chaos case in this export.</p>}
          {c.hidden_generic ? <HiddenGeneric card={c.hidden_generic} /> : <p className="empty">No hidden-generic case in this export.</p>}
          {c.egfr_pair ? <EgfrBlindness card={c.egfr_pair} /> : <p className="empty">No eGFR pair in this export.</p>}
          {c.alert_fatigue ? <AlertFatigue card={c.alert_fatigue} /> : <p className="empty">No alert-fatigue case in this export.</p>}
        </>
      )}
      <p className="meta" style={{ marginTop: 24 }}>{plural(x.source.patients, 'patient')} exported by <span className="mono">{x.source.command}</span>. {SEVERITY_LABEL.major} and {SEVERITY_LABEL.contraindicated.toLowerCase()} count as serious.</p>
    </div>
  );
}
