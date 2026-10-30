// The public home page. Every figure on it is read from the pipeline's data file
// (public/data/pipeline.json): the evaluation report, the standard-check reproduction and the
// demo cases. The page computes nothing; it chooses which exported numbers to show.

import { Link } from 'react-router-dom';
import type { OfficialScore } from '../data/contract';
import { ISSUE_LABEL, num, plural } from '../data/format';
import { useData } from '../data/load';
import { Architecture } from '../components/Architecture';
import { StatusInline } from '../components/ui';
import { fmtEgfr } from './PatientDetail';

function Score({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="home-score">
      <span className="home-score-k">{label}</span>
      <span className="home-score-v mono" style={{ color: tone }}>{value}</span>
      <span className="home-score-s">{sub}</span>
    </div>
  );
}

export function Nav() {
  return (
    <header className="home-nav">
      <div className="home-wrap home-nav-inner">
        <Link to="/" className="lp-brand"><span className="brand-mark" aria-hidden="true" />Medsafe</Link>
        <nav className="home-links" aria-label="On this page">
          <a href="#problem">The problem</a><a href="#two-screens">Two screens</a><a href="#how">How it works</a>
          <a href="#ward">The ward</a><a href="#results">Results</a><Link to="/models">Architecture and models</Link>
        </nav>
        <span className="chip">Prototype · simulated dataset</span>
        <Link className="btn btn-primary btn-sm" to="/login">Sign in</Link>
      </div>
    </header>
  );
}

export function Home() {
  const { x, byId } = useData();
  const holdout = x.evaluation.report?.splits.holdout;
  const ours: OfficialScore | undefined = holdout?.official;
  const ehr = x.ehr_reference.score?.official;
  const pack = holdout?.baselines['pack baseline'];
  const cards = x.demo?.cards;
  const fatigue = cards?.alert_fatigue;
  const loud = fatigue ? byId.get(fatigue.patient_id) : undefined;
  const pair = cards?.egfr_pair;
  const chaos = cards?.brand_chaos;
  const hidden = cards?.hidden_generic;
  const chaosP = chaos ? byId.get(chaos.patient_id) : undefined;
  const hiddenP = hidden ? byId.get(hidden.patient_id) : undefined;
  const pairLine = pair ? byId.get(pair.low.patient_id)?.medications[pair.low.line].raw : undefined;

  return (
    <div className="home">
      <Nav />

      <section className="home-hero">
        <div className="home-wrap home-hero-grid">
          <div>
            <p className="lp-kicker">Medication safety, a second pair of eyes</p>
            <h1 className="home-h1">Every alert earns its place.<br />The serious ones come first.</h1>
            <p className="home-lead">
              A ward nurse copies every medicine a patient brings onto one list: brands, generics, abbreviations and misspellings, from up to
              three prescribers. Medsafe reads that list as written, checks it against the reference tables, and shows the prescriber what to
              change first. A clinician decides.
            </p>
            <div className="home-ctas">
              <Link className="btn btn-primary" to="/login">Sign in to the demo</Link>
              <Link className="btn btn-secondary" to="/app/why">Four ways a standard check fails</Link>
            </div>
          </div>
          {loud && fatigue && (
            <aside className="home-case" aria-label={`One real patient: ${loud.id}`}>
              <p className="home-case-k">One patient from the training set, <span className="mono">{loud.id}</span></p>
              <div className="home-case-row">
                <span className="home-case-who">Standard EHR check</span>
                <span className="home-case-big mono">{loud.compare.ehr.alerts}</span>
                <span className="home-case-what">alerts. <span className="mono">{fatigue.serious_raised}</span> of the <span className="mono">{fatigue.serious_labelled}</span> serious issues are among them; <span className="mono">{loud.compare.ehr.not_in_formulary}</span> medicines on the list were never checked.</span>
              </div>
              <div className="home-case-row home-case-us">
                <span className="home-case-who">Medsafe</span>
                <span className="home-case-big mono">{loud.compare.medsafe.actions ?? '—'}</span>
                <span className="home-case-what">actions, {loud.compare.medsafe.to_verify === 0 ? 'every line resolved' : <><span className="mono">{loud.compare.medsafe.to_verify}</span> lines to verify manually</>}, <span className="mono">{loud.compare.medsafe.combinations_expanded}</span> combination brands opened{loud.medsafe.collapse?.summary ? `. ${loud.medsafe.collapse.summary}` : '.'}</span>
              </div>
              <ul className="home-case-missed" aria-label="Serious issues the standard check did not raise">
                {fatigue.missed.slice(0, 4).map((l) => (
                  <li key={`${l.issue_type}${l.drugs.join()}`}><StatusInline severity={l.severity} /> {ISSUE_LABEL[l.issue_type]}, <span className="mono">{l.drugs.join(' + ')}</span>: missed by the standard check</li>
                ))}
              </ul>
              <Link className="home-case-open" to={`/app/patient/${loud.id}?mode=ehr`}>Open this patient →</Link>
            </aside>
          )}
        </div>
      </section>

      {ours && (
        <section id="results" className="home-proof" aria-label="Results">
          <div className="home-wrap">
            <div className="home-scores">
              <Score label="Score, organisers' evaluate.py" value={num(ours.primary_score, 3)} sub={`Standard EHR check ${ehr ? num(ehr.primary_score, 3) : '—'} · organisers' baseline ${pack ? num(pack.primary_score, 3) : '—'}`} tone="var(--action)" />
              <Score label="Serious issues caught" value={num(ours.components.serious_recall)} sub={`${ours.counts.true_serious} serious issues in the labels`} />
              <Score label="Seeded near-misses caught" value={`${holdout!.near_misses.filter((n) => n.status === 'caught').length} / ${holdout!.near_misses.length}`} sub="Hard cases: misspellings, hidden combinations, eGFR at a threshold" />
              <Score label="Noise alerts per patient" value={num(ours.components.noise_alerts_per_patient)} sub={`Standard EHR check ${ehr ? num(ehr.components.noise_alerts_per_patient) : '—'}`} tone="var(--ok)" />
            </div>
            <p className="home-caveat">
              <span className="mono">{holdout!.patients}</span> training patients held out from tuning, scored by the organisers' unmodified <span className="mono">evaluate.py</span>.
              The rules' vocabulary was built on all training text, so these figures are optimistic for the hidden test set. <Link to="/app/evaluation">Every number, with the misses →</Link>
            </p>
          </div>
        </section>
      )}

      <section id="problem" className="home-section">
        <div className="home-wrap">
          <h2 className="home-h2">The warning that matters gets lost among the ones that do not.</h2>
          <p className="home-lead home-measure">
            Clinicians override 49% to 96% of drug-safety alerts in computerised order entry.<sup><a href="#ref-1">1</a></sup> And a standard check
            that only knows exact names does not see much of a handwritten list. Three real cases from this dataset:
          </p>
          <div className="home-three">
            <article className="home-card">
              <h3 className="lp-h3">One medicine, written twice</h3>
              {chaos && chaosP && <p className="home-card-quote mono">{chaos.lines.map((i) => `"${chaosP.medications[i].raw}"`).join('  ·  ')}</p>}
              <p>Both are {chaos?.generic ?? 'the same drug'}. The standard check knows one of the names, so it never sees the duplicate.</p>
            </article>
            <article className="home-card">
              <h3 className="lp-h3">A generic hidden in a brand</h3>
              {hidden && hiddenP && <p className="home-card-quote mono">{[...hidden.combination_lines, ...hidden.other_lines].map((i) => `"${hiddenP.medications[i].raw}"`).join('  ·  ')}</p>}
              <p>The combination brand contains {hidden?.generic ?? 'a second dose'}. Unopened, it is one unknown product, and the double dose goes through.</p>
            </article>
            <article className="home-card">
              <h3 className="lp-h3">Kidney function ignored</h3>
              {pair && pairLine && <p className="home-card-quote mono">"{pairLine}" at eGFR {fmtEgfr(pair.low.egfr)} and {fmtEgfr(pair.high.egfr)}</p>}
              <p>
                The standard check fires the same {pair?.generic ?? 'renal'} warning for both. The renal rules are tiered by kidney function:
                {pair ? <> Medsafe raises it as {pair.label.severity} at eGFR {fmtEgfr(pair.low.egfr)}{pair.high.medsafe_alert === null ? <> and raises nothing at {fmtEgfr(pair.high.egfr)}</> : null}.</> : null}
              </p>
            </article>
          </div>
          <Link className="home-more" to="/app/why">See all four, side by side →</Link>
        </div>
      </section>

      {loud && (
        <section id="two-screens" className="home-section home-alt">
          <div className="home-wrap">
            <h2 className="home-h2">The same list, two screens.</h2>
            <p className="home-lead home-measure">One switch on every patient flips between a reproduction of a standard hospital check and Medsafe, on the same reference tables.</p>
            <div className="home-compare">
              <div className="home-compare-row">
                <span className="home-compare-k">Standard EHR check</span>
                <span><span className="mono">{loud.compare.ehr.alerts}</span> alerts · <span className="mono">{loud.compare.ehr.not_in_formulary}</span> medicines not in formulary · <span className="mono">{loud.compare.ehr.combinations_unexpanded}</span> combinations not opened · eGFR not read</span>
              </div>
              <div className="home-compare-row on">
                <span className="home-compare-k">Medsafe</span>
                <span><span className="mono">{loud.compare.medsafe.actions ?? '—'}</span> actions · <span className="mono">{loud.compare.medsafe.dropped}</span> lines dropped · <span className="mono">{loud.compare.medsafe.combinations_expanded}</span> combinations opened · eGFR {loud.egfr === null ? 'not recorded' : <span className="mono">{fmtEgfr(loud.egfr)}</span>}</span>
              </div>
            </div>
          </div>
        </section>
      )}

      <section id="how" className="home-section">
        <div className="home-wrap">
          <h2 className="home-h2">Four steps between the list and the decision.</h2>
          <ol className="home-steps">
            <li><span className="home-step-n mono">01</span><h3 className="lp-h3">Read every line</h3><p>Brands, misspellings, abbreviations and combination brands resolve to generics with a confidence. A name too close to call is marked "verify manually", never guessed.</p></li>
            <li><span className="home-step-n mono">02</span><h3 className="lp-h3">Check the tables</h3><p>Interactions, duplicate therapy, kidney dose by eGFR tier, and drug-condition contraindications, each with the table's own severity and action.</p></li>
            <li><span className="home-step-n mono">03</span><h3 className="lp-h3">Put the important one first</h3><p>Alerts are ordered by severity. When one drug sits in several serious interactions, the screen leads with "review that drug first". Minor issues come last.</p></li>
            <li><span className="home-step-n mono">04</span><h3 className="lp-h3">A clinician decides</h3><p>Every alert carries its rule, its confidence and what could not be checked. The prescriber accepts, overrides with a reason, or hands it to a pharmacist.</p></li>
          </ol>
          <p className="home-note">No model decides anything. Three trained models were measured against the rules and are reported on the evaluation page; the rules held.</p>
        </div>
      </section>

      <section id="built" className="home-section home-alt">
        <div className="home-wrap">
          <h2 className="home-h2">What it is built from.</h2>
          <p className="home-lead home-measure">One deterministic Python engine writes the submission files and serves the ward. No language model anywhere, no network at runtime.</p>
          <Architecture />
          <figure className="model-fig" style={{ marginTop: 32 }}>
            <h3 className="lp-h3">Three trained models, measured against the rules on the holdout split</h3>
            <img src={`${import.meta.env.BASE_URL}figures/2_scores.png`} alt="Official scores: rules against each trained model, and a standard EHR check with and without learned triage" loading="lazy" />
            <figcaption>Drawn by <span className="mono">eval/ml_plots.py</span> from the organisers' scorer. <Link to="/models">All the graphs, with training curves →</Link></figcaption>
          </figure>
        </div>
      </section>

      <section id="ward" className="home-section home-alt">
        <div className="home-wrap">
          <h2 className="home-h2">A ward, end to end.</h2>
          <ol className="home-flow">
            <li><strong>Nurse</strong><span>Admits the patient, pulls their records through ABHA with consent (a simulated sandbox here), and adds what the patient brought.</span></li>
            <li><strong>Lab technician</strong><span>Enters eGFR. The kidney-dose rules re-run on it.</span></li>
            <li><strong>Pharmacist</strong><span>Confirms the names the system would not guess, and answers deferred alerts.</span></li>
            <li><strong>Prescriber</strong><span>Accepts, overrides with a reason, or defers each alert.</span></li>
            <li><strong>Audit log</strong><span>Every entry and decision, with who and when. Which alerts get overridden most, and why.</span></li>
          </ol>
          <p className="home-note">Every check runs the real pipeline on the ward server; the ward runs locally with <span className="mono">python tools/serve_ui.py</span>.</p>
        </div>
      </section>

      <section className="home-section">
        <div className="home-wrap home-three">
          <article className="home-card"><h3 className="lp-h3">Says what it could not check</h3><p>With nothing found it says "no issue was found in the medicines listed; the list may be incomplete", and names every line and value it could not check.</p></article>
          <article className="home-card"><h3 className="lp-h3">Abstains instead of guessing</h3><p>A confidently wrong name hides a real interaction. A line it cannot read is shown to a person as "verify manually" and kept out of the checks.</p></article>
          <article className="home-card"><h3 className="lp-h3">Reports its caveats</h3><p>Synthetic data, simplified tables, a sandbox for ABHA, and figures that are optimistic for the hidden set: each is stated where it applies.</p></article>
        </div>
      </section>

      <footer className="home-foot">
        <div className="home-wrap">
          <p id="ref-1" className="home-ref">
            1. van der Sijs H, Aarts J, Vulto A, Berg M. Overriding of drug safety alerts in computerized physician order entry.
            J Am Med Inform Assoc. 2006;13(2):138–147.
          </p>
          <p className="home-ref">
            Prototype on the synthetic H4 dataset ({plural(x.source.patients, 'training patient')} shown). Drug facts are simplified for the
            challenge and are not a clinical reference. No real patient data.
          </p>
          <div className="home-foot-row"><span className="lp-brand"><span className="brand-mark" aria-hidden="true" />Medsafe</span><Link to="/login">Sign in</Link></div>
        </div>
      </footer>
    </div>
  );
}
