import { Link } from 'react-router-dom';
import { DRUGS, EXPANDED_PAIR_COUNT, INTERACTIONS } from '../data/drugs';
import { BY_ID, name } from '../data/engine';
import { CONTROL_ID, HERO_ID } from '../data/patients';
import { AlertGraph } from '../components/AlertGraph';
import { MethodDiagram } from '../components/Charts';
import { StatusInline } from '../components/ui';

function RenalCard({ id }: { id: string }) {
  const x = BY_ID[id];
  const alert = x.all.find((a) => a.key === 'renal:MTF')!;
  const raw = x.patient.meds.find((m) => m.code === 'MTF')!.raw;
  return (
    <div className="card">
      <div className="head">
        <Link to={`/patient/${id}`} className="mono">Patient {id}</Link>
        <StatusInline level={alert.severity} />
      </div>
      <div className="big">eGFR {x.patient.egfr}</div>
      <div className="row"><span className="k">As written</span><span className="mono">"{raw}"</span></div>
      <div className="row"><span className="k">Resolved</span><span className="mono">metformin 500 mg</span></div>
      <div className="row"><span className="k">Age</span><span className="mono">{x.patient.age}</span></div>
      <div className="row"><span className="k">Table severity</span><span>renal flag</span></div>
      <div className="act">{alert.action}</div>
    </div>
  );
}

export function Method() {
  const hero = BY_ID[HERO_ID];
  const anchor = hero.anchors[0];
  return (
    <div className="content narrow">
      <div className="page-head">
        <h1 className="display">How it works</h1>
        <p className="meta">Four deterministic steps. Every suggested action comes from the committed rule tables, not from a model.</p>
      </div>

      <MethodDiagram />

      <div className="prose">
        <h2 className="section">Severity is re-scored per patient</h2>
        <p>
          A rule table says a pair or a drug is risky in general. Whether it is risky for <em>this</em> patient depends on kidney
          function, age and weight. The same metformin 500 mg flag, on two patients:
        </p>
        <div className="pair">
          <RenalCard id={HERO_ID} />
          <RenalCard id={CONTROL_ID} />
        </div>
        <p>
          Both severities are stored. The table severity is shown next to the re-scored one on every alert, so a reviewer
          can see why a moderate interaction became high.
        </p>

        <h2 className="section">One change, not five alerts</h2>
        <p>
          Drugs are nodes; serious interactions are edges. The system checks which single drug, among those the rule table
          allows stopping, clears the most serious edges. For patient <Link to={`/patient/${HERO_ID}`} className="mono">{HERO_ID}</Link>,
          stopping <strong>{name(anchor)}</strong> clears <span className="mono">{hero.clearedByAnchor}</span> of
          the <span className="mono">{hero.serious}</span>. Warfarin, lithium and insulin are never suggested for stopping,
          however many edges they carry.
        </p>
        <div className="pair">
          <div className="card">
            <div className="label">Before: {hero.serious} serious interactions</div>
            <AlertGraph analysis={hero} width={300} height={220} />
          </div>
          <div className="card">
            <div className="label">After stopping {name(anchor)}: {hero.serious - hero.clearedByAnchor} left</div>
            <AlertGraph analysis={hero} width={300} height={220} removed />
          </div>
        </div>
        <p>
          The capped list then ranks what is left by severity and confidence and shows at most five. Low-severity notes are
          never in the capped list; they stay one click away under every pair.
        </p>

        <h2 className="section">What the system never says</h2>
        <p>
          It never calls a patient safe. When nothing is flagged it says <strong>no issue was found in what was seen</strong>,
          states how many medicines it could not resolve, and a permanent footer on every patient says a clinician decides.
          A name it cannot resolve with a clear margin is shown as unresolved, not guessed.
        </p>

        <h2 className="section">What is real and what is not</h2>
        <dl className="truth">
          <dt>Real</dt>
          <dd>The drug interactions and renal rules (clinically genuine, commonly cited). The patient-context re-scoring, the graph collapse and the five-alert cap, which run over the data shown here.</dd>
          <dt>Simulated</dt>
          <dd>All patients and medication lists. The name-resolution outputs and their ground-truth labels, and the near-miss labels, are fixtures. No real patient data was used.</dd>
          <dt>Reduced</dt>
          <dd><span className="mono">{DRUGS.length}</span> generics and <span className="mono">{INTERACTIONS.length}</span> interaction rules, expanding to <span className="mono">{EXPANDED_PAIR_COUNT}</span> drug pairs, rather than the full reference set. Sized for the demo.</dd>
          <dt>Offline</dt>
          <dd>No backend and no network. The rule pass runs over committed data, so the same inputs give the same screen every time.</dd>
        </dl>
      </div>
    </div>
  );
}
