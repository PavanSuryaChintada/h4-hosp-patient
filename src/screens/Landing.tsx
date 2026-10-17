import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth';
import { DRUGS, EXPANDED_PAIR_COUNT, INTERACTIONS } from '../data/drugs';
import { BY_ID, METRICS, name, type Alert } from '../data/engine';
import { NEAR_MISS } from '../data/evaluation';
import { HERO_ID } from '../data/patients';
import { AlertGraph } from '../components/AlertGraph';
import { Segmented } from '../components/ui';

const hero = BY_ID[HERO_ID];
const SEV_LABEL = { high: 'High', medium: 'Medium', low: 'Low' };
const DEFAULT_SEV: Record<string, string> = { major: 'high', moderate: 'medium', minor: 'low' };
const resolutionPct = Math.round((METRICS.resolution.fuzzyCorrect / METRICS.resolution.fuzzy) * 100);

const NAV = [
  { href: '#problem', label: 'Problem' },
  { href: '#architecture', label: 'Architecture' },
  { href: '#end-to-end', label: 'End to end' },
  { href: '#difference', label: 'What is different' },
  { href: '#stack', label: 'Tech stack' },
  { href: '#walkthrough', label: 'Walkthrough' },
];

function AlertLine({ a }: { a: Alert }) {
  return (
    <li className={`demo-row s-${a.severity}`}>
      <span className="demo-sev"><span className="sq" aria-hidden="true" />{SEV_LABEL[a.severity]}</span>
      <span className="demo-act">{a.action}</span>
    </li>
  );
}

/** The hero: patient 2291's real alert list, every pair against collapsed. */
function CollapseDemo() {
  const [mode, setMode] = useState<'all' | 'collapsed'>('all');
  const rows = mode === 'all' ? hero.all : hero.collapsed;
  const anchor = hero.anchors[0];
  const about = hero.all.filter((a) => a.drugs.includes(anchor)).length;
  const shown = new Set(hero.collapsed.map((a) => a.key));
  const folded = hero.all.filter((a) => !shown.has(a.key) && a.severity !== 'low');
  const notes = hero.all.filter((a) => a.severity === 'low');
  const lows = notes.length;
  const label = (a: Alert) => a.drugs.map(name).join(' + ') + (a.kind === 'renal' ? ', renal dose' : '');
  return (
    <section className="demo" aria-label={`Live demo: patient ${HERO_ID}`}>
      <div className="demo-head">
        <div>
          <div className="demo-title">Patient <span className="mono">{HERO_ID}</span></div>
          <div className="meta"><span className="mono">74</span> years, eGFR <span className="mono">28</span>, <span className="mono">9</span> medicines</div>
        </div>
        <Segmented label="Alert view" value={mode} onChange={setMode} segments={[
          { value: 'all', label: `Every pair (${hero.all.length})` },
          { value: 'collapsed', label: `Collapsed (${hero.collapsed.length})` },
        ]} />
      </div>
      <p className="demo-cap">
        {mode === 'all'
          ? `What a typical checker shows: ${hero.all.length} alerts, ${about} about one drug, ${lows} low severity.`
          : `What Medsafe shows: one decision per cluster, capped at five, with every action taken from a rule.`}
      </p>
      <ul className="demo-rows">
        {rows.map((a) => <AlertLine key={a.key} a={a} />)}
        {mode === 'collapsed' && (
          <>
            <li className="demo-fold">
              <div className="demo-fold-head">Folded into the {name(anchor)} row ({folded.length})</div>
              <ul>{folded.map((a) => <li key={a.key}>{label(a)}</li>)}</ul>
            </li>
            <li className="demo-fold">
              <div className="demo-fold-head">Kept as low-severity notes, one click away ({notes.length})</div>
              <ul>{notes.map((a) => <li key={a.key}>{label(a)}</li>)}</ul>
            </li>
          </>
        )}
      </ul>
    </section>
  );
}

function Architecture() {
  return (
    <figure className="arch" aria-label="Architecture: prescription slip to prescriber view in four stages">
      <div className="arch-grid">
        <div className="arch-box arch-io">
          <div className="arch-kicker">Input</div>
          <h3>Prescription slip</h3>
          <p>The medicine list as written: brand or generic, misspelt, with dose and form.</p>
          <p className="arch-eg mono">"Warf 5", "crocine", "PAN-D"</p>
        </div>
        <div className="arch-box arch-fixture">
          <div className="arch-kicker"><span className="mono">1</span> Resolve names</div>
          <h3>Read what was meant</h3>
          <p>Normalise the text, generate candidates by edit distance and character trigrams, rerank. Abstain when the top two are too close.</p>
          <p className="arch-out">Out: a generic with a confidence, or "verify manually"</p>
        </div>
        <div className="arch-box">
          <div className="arch-kicker"><span className="mono">2</span> Check rules</div>
          <h3>Find every issue</h3>
          <p>Interaction pairs from class-level rules, duplicate therapy, renal dose against eGFR, pregnancy.</p>
          <p className="arch-out">Out: findings with their table severity and rule id</p>
        </div>
        <div className="arch-box">
          <div className="arch-kicker"><span className="mono">3</span> Re-score in context</div>
          <h3>Judge for this patient</h3>
          <p>Each rule carries a modifier: renal, bleeding, sedation or age. The same flag rises or falls with the patient.</p>
          <p className="arch-out">Out: table severity and patient severity, both kept</p>
        </div>
        <div className="arch-box">
          <div className="arch-kicker"><span className="mono">4</span> Collapse and cap</div>
          <h3>One change per cluster</h3>
          <p>Drugs are nodes, serious interactions are edges. Pick the stoppable drug that clears the most, rank the rest, keep five.</p>
          <p className="arch-out">Out: at most five alerts, each with an action</p>
        </div>
        <div className="arch-box arch-io">
          <div className="arch-kicker">Output</div>
          <h3>Prescriber view</h3>
          <p>Capped alerts, the alert graph, the slip next to its matches, and a footer that says a clinician decides.</p>
        </div>

        <div className="arch-feed arch-feed-ref">
          <h4>Reference tables</h4>
          <p><span className="mono">{DRUGS.length}</span> generics with Indian brand names, <span className="mono">{INTERACTIONS.length}</span> interaction rules covering <span className="mono">{EXPANDED_PAIR_COUNT}</span> drug pairs, renal thresholds, pregnancy rules.</p>
          <p className="arch-feeds">Feeds stages 1 and 2</p>
        </div>
        <div className="arch-feed arch-feed-ctx">
          <h4>Patient context</h4>
          <p>Age, weight, eGFR, pregnancy status.</p>
          <p className="arch-feeds">Feeds stage 3</p>
        </div>
        <div className="arch-feed arch-feed-eval">
          <h4>Evaluation harness</h4>
          <p>Ground-truth names, <span className="mono">{NEAR_MISS.seeded}</span> seeded near-misses, and the cases that were missed.</p>
          <p className="arch-feeds">Measures stage 4 and the output</p>
        </div>
      </div>
      <figcaption className="arch-legend">
        <span><span className="lg lg-solid" aria-hidden="true" />Runs live in this prototype</span>
        <span><span className="lg lg-dashed" aria-hidden="true" />Precomputed in this prototype: name-matching results are fixtures</span>
      </figcaption>
    </figure>
  );
}

function EndToEnd() {
  const raw = (code: string | null, rawText?: string) => hero.patient.meds.find((m) => (rawText ? m.raw === rawText : m.code === code))!;
  const examples = [raw('WAR'), raw(null, 'crocine'), raw(null, 'PAN-D')];
  const kinds = [
    { label: 'Interactions', n: hero.all.filter((a) => a.kind === 'interaction').length },
    { label: 'Renal dose', n: hero.all.filter((a) => a.kind === 'renal').length },
    { label: 'Duplicate therapy', n: hero.all.filter((a) => a.kind === 'duplicate').length },
  ];
  const rescored = hero.all.filter((a) => a.kind === 'interaction' && a.rescored && DEFAULT_SEV[a.tableSeverity] !== a.severity);

  return (
    <ol className="e2e">
      <li className="e2e-step">
        <div className="e2e-label"><span className="e2e-n mono">1</span><h3>Read as written</h3><p>{hero.checked} of {hero.patient.meds.length} lines resolve. One is too close to call and goes to a manual check instead of a guess.</p></div>
        <div className="e2e-card">
          {examples.map((m) => (
            <div key={m.raw} className={`e2e-med${m.code ? '' : ' abst'}`}>
              <span className="mono ink-3">"{m.raw}"</span>
              <span className="ink-3" aria-hidden="true">→</span>
              <span className="e2e-res">{m.code ? name(m.code) : 'could not resolve'}</span>
              <span className="mono">{m.code ? m.confidence.toFixed(2) : m.candidates!.map(([, s]) => s.toFixed(2)).join(' vs ')}</span>
            </div>
          ))}
        </div>
      </li>
      <li className="e2e-step">
        <div className="e2e-label"><span className="e2e-n mono">2</span><h3>Checked against the rules</h3><p>Every pair and every drug is checked. This is the full list a typical checker would show.</p></div>
        <div className="e2e-card">
          <table className="e2e-table">
            <tbody>
              {kinds.map((k) => <tr key={k.label}><td>{k.label}</td><td className="num">{k.n}</td></tr>)}
              <tr className="tot"><td>Findings</td><td className="num">{hero.all.length}</td></tr>
            </tbody>
          </table>
        </div>
      </li>
      <li className="e2e-step">
        <div className="e2e-label"><span className="e2e-n mono">3</span><h3>Re-scored for this patient</h3><p>At eGFR 28, two moderate interactions that strain the kidneys become high. The table value stays on record next to the new one.</p></div>
        <div className="e2e-card">
          {rescored.map((a) => (
            <div key={a.key} className="e2e-rescore">
              <span>{a.drugs.map(name).join(' + ')}</span>
              <span className="mono"><span className="ink-3">{a.tableSeverity}</span> to <span style={{ color: 'var(--critical)' }}>high</span></span>
            </div>
          ))}
        </div>
      </li>
      <li className="e2e-step">
        <div className="e2e-label"><span className="e2e-n mono">4</span><h3>Collapsed to one decision</h3><p>Diclofenac sits on {hero.clearedByAnchor} of the {hero.serious} serious interactions, and the rule table allows stopping it. Warfarin is never offered.</p></div>
        <div className="e2e-card e2e-graph"><AlertGraph analysis={hero} width={360} height={220} /></div>
      </li>
      <li className="e2e-step">
        <div className="e2e-label"><span className="e2e-n mono">5</span><h3>Shown to the prescriber</h3><p>{hero.collapsed.length} alerts instead of {hero.all.length}, each with an action and its rule, and a footer that keeps the decision with the clinician.</p></div>
        <div className="e2e-card">
          <ul className="demo-rows demo-rows-tight">{hero.collapsed.map((a) => <AlertLine key={a.key} a={a} />)}</ul>
        </div>
      </li>
    </ol>
  );
}

const DIFF = [
  ['Input', 'Expects clean generic names picked from a list', 'Reads the slip as written: brands, misspellings, dose suffixes'],
  ['Unclear names', 'Guesses silently, or drops the line', 'Abstains and marks the line "verify manually, not checked"'],
  ['Severity', 'One fixed severity per pair, for every patient', 'Re-scored for eGFR, age and weight, with the table value kept'],
  ['Output', 'One alert per risky pair', 'One alert per cluster: the change that clears the most'],
  ['Volume', 'Every pair, every time', 'At most five; low-severity notes one click away'],
  ['Nothing found', '"No interactions"', '"No issue found in what was seen. A clinician decides."'],
  ['Evaluation', 'Alert counts, if anything', 'Alert volume and near-miss recall together, misses listed'],
];

const STACK = [
  ['React', '18.3', 'Screens, state and the walkthrough'],
  ['TypeScript', '5.6, strict', 'The rule engine and every data table are typed'],
  ['Vite', '5.4', 'Dev server and production build'],
  ['React Router', '6.28', 'Client-side routing and deep links'],
  ['Hand-written SVG', 'no library', 'Alert graph, charts and diagrams'],
  ['CSS custom properties', 'one token file', 'IBM Plex, square corners, status-only colour'],
];

export function Landing() {
  const { user } = useAuth();
  const demoHref = user ? '/app' : '/login';
  return (
    <div className="lp">
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-inner">
          <Link to="/" className="lp-brand">Medsafe</Link>
          <nav aria-label="Sections" className="lp-links">
            {NAV.map((n) => <a key={n.href} href={n.href}>{n.label}</a>)}
          </nav>
          <div className="lp-nav-cta">
            <span className="chip">Prototype on simulated data</span>
            <Link to={demoHref} className="btn btn-primary btn-sm">{user ? 'Open the app' : 'Sign in'}</Link>
          </div>
        </div>
      </header>

      <main>
        <section className="lp-hero">
          <div className="lp-wrap lp-hero-grid">
            <div className="lp-hero-copy">
              <p className="lp-kicker">Medication safety, a second pair of eyes</p>
              <h1 className="lp-h1"><span>Eleven warnings.</span> <span>One decision.</span></h1>
              <p className="lp-lead">
                Medsafe reads a prescription the way it was written, checks it against clinical rules, re-scores every flag for
                the patient in front of you, and turns each cluster of alerts into the one change that clears it.
              </p>
              <div className="lp-ctas">
                <Link to={demoHref} className="btn btn-primary">Open the live demo</Link>
                <Link to="/login?tour=1" className="btn btn-secondary">Take the guided walkthrough</Link>
              </div>
              <p className="lp-hint">Try the toggle on the right. It is the real output for patient {HERO_ID}.</p>
            </div>
            <CollapseDemo />
          </div>
        </section>

        <section className="lp-proof" aria-label="Results on the simulated cohort">
          <div className="lp-wrap">
            <dl className="proof-grid">
              <div><dt>Patient {HERO_ID}</dt><dd className="mono">{hero.all.length} to {hero.collapsed.length}</dd><p>alerts, every pair against collapsed</p></div>
              <div><dt>Across {METRICS.patients} patients</dt><dd className="mono">{METRICS.alertsBefore.toFixed(1)} to {METRICS.alertsAfter.toFixed(1)}</dd><p>mean alerts per patient</p></div>
              <div><dt>Near-miss recall</dt><dd className="mono">{NEAR_MISS.caught} / {NEAR_MISS.seeded}</dd><p>seeded serious cases still flagged after the collapse</p></div>
              <div><dt>Misspelled names</dt><dd className="mono">{resolutionPct}%</dd><p>matched correctly; {METRICS.resolution.abstained} abstained instead of guessing</p></div>
            </dl>
            <p className="proof-note">Measured on a simulated 40-patient cohort. No real patient data. <a href="#honesty">What is real and what is not</a></p>
          </div>
        </section>

        <section id="problem" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">The warning that matters gets lost among the ones that do not.</h2>
            <p className="lp-lead lp-measure">
              Interaction checkers warn on every risky pair, at the same severity for every patient. A prescriber with four minutes
              per patient learns to click through them. Studies of computerised order entry report clinicians overriding 49% to 96%
              of drug safety alerts.<sup><a href="#ref-1" id="cite-1">1</a></sup>
            </p>
            <div className="lp-three">
              <div className="lp-cell">
                <h3 className="lp-h3">Slips are messy</h3>
                <p>Brands, generics, misspellings and dose suffixes on one list: <span className="mono">"Warf 5"</span>, <span className="mono">"crocine"</span>, <span className="mono">"PAN-D"</span>. Tools that expect clean names miss lines or match them wrongly.</p>
              </div>
              <div className="lp-cell">
                <h3 className="lp-h3">One alert per pair</h3>
                <p>Patient {HERO_ID} takes nine medicines and triggers eleven warnings. Five of them are about the same drug, and three are low severity.</p>
              </div>
              <div className="lp-cell">
                <h3 className="lp-h3">Context is ignored</h3>
                <p>A renal flag for metformin fires the same way at eGFR 28 and at eGFR 80. At 28 it should stop the prescription; at 80 it is a yearly check.</p>
              </div>
            </div>
          </div>
        </section>

        <section id="architecture" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <h2 className="lp-h2">Four steps between the slip and the screen.</h2>
            <p className="lp-lead lp-measure">
              Each step records why it decided what it did, so the prescriber sees the reason next to the alert. No model writes an
              action: every suggestion traces back to a rule id such as <span className="mono">NSAID-ACEI-01</span>.
            </p>
            <Architecture />
          </div>
        </section>

        <section id="end-to-end" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">One prescription, end to end.</h2>
            <p className="lp-lead lp-measure">
              Patient {HERO_ID}: 74 years old, eGFR 28, nine medicines. Each panel below is what the app actually computes for her,
              not an illustration.
            </p>
            <EndToEnd />
          </div>
        </section>

        <section id="difference" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <h2 className="lp-h2">What changes compared with a typical checker.</h2>
            <div className="diff-wrap">
              <table className="diff">
                <thead>
                  <tr><th scope="col"><span className="sr-only">Aspect</span></th><th scope="col">Typical interaction checker</th><th scope="col" className="diff-us">Medsafe</th></tr>
                </thead>
                <tbody>
                  {DIFF.map(([k, them, us]) => (
                    <tr key={k}><th scope="row">{k}</th><td>{them}</td><td className="diff-us">{us}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div id="honesty" className="lp-three lp-trust">
              <div className="lp-cell">
                <h3 className="lp-h3">It never calls a patient safe</h3>
                <p>When nothing is flagged it says no issue was found in what was seen, counts what it could not check, and leaves the decision with the clinician.</p>
              </div>
              <div className="lp-cell">
                <h3 className="lp-h3">It abstains instead of guessing</h3>
                <p>A name that sits too close to two candidates is shown as unresolved and excluded from the checks, so a wrong match cannot hide a real interaction.</p>
              </div>
              <div className="lp-cell">
                <h3 className="lp-h3">It reports its misses</h3>
                <p>The evaluation lists both missed near-misses and why they were missed. Real: rules, re-scoring, collapse and cap. Simulated: patients, name-matching results and near-miss labels.</p>
              </div>
            </div>
          </div>
        </section>

        <section id="stack" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">A small stack, on purpose.</h2>
            <p className="lp-lead lp-measure">
              No backend, no database and no model in the request path. The rule pass is deterministic: the same prescription gives
              the same screen every time, which is what a safety tool owes the person reading it.
            </p>
            <div className="stack-grid">
              {STACK.map(([n, v, why]) => (
                <div key={n} className="stack-item">
                  <div className="stack-name">{n} <span className="mono ink-3">{v}</span></div>
                  <p>{why}</p>
                </div>
              ))}
            </div>

            <h3 className="lp-h3 lp-sub">How it ships</h3>
            <ol className="ship">
              <li><span className="mono">1</span><strong>GitHub</strong><p>Push to <span className="mono">main</span></p></li>
              <li><span className="mono">2</span><strong>Build</strong><p><span className="mono">npm ci</span>, strict type-check, Vite build</p></li>
              <li><span className="mono">3</span><strong>Static hosting</strong><p>Vercel or GitHub Pages, with every route served by the app</p></li>
              <li><span className="mono">4</span><strong>Browser</strong><p>React app, rule engine and data run on the device</p></li>
            </ol>

            <h3 className="lp-h3 lp-sub">Next, not built yet</h3>
            <ul className="next-list">
              <li>A name-matching service in place of the precomputed results, with the same abstention rule.</li>
              <li>Licensed drug reference data in place of the reduced tables.</li>
              <li>Hospital record integration through HL7 FHIR medication requests.</li>
              <li>Prospective evaluation against near-misses labelled by pharmacists.</li>
            </ul>
          </div>
        </section>

        <section id="walkthrough" className="lp-section lp-section-alt">
          <div className="lp-wrap lp-walk">
            <div>
              <h2 className="lp-h2">See it in two minutes.</h2>
              <p className="lp-lead">
                Sign in with a demo account and a guided walkthrough starts on its own. It moves through the app for you and
                highlights one thing at a time.
              </p>
              <div className="lp-ctas">
                <Link to="/login?tour=1" className="btn btn-primary">Start the walkthrough</Link>
                <Link to={demoHref} className="btn btn-secondary">Explore on my own</Link>
              </div>
            </div>
            <ol className="walk-list">
              <li><strong>The queue</strong><span>Forty prescriptions ranked by urgency</span></li>
              <li><strong>Patient {HERO_ID}</strong><span>Context first: eGFR 28, nine medicines</span></li>
              <li><strong>The collapse</strong><span>Eleven alerts to three, in one click</span></li>
              <li><strong>The alert graph</strong><span>Why stopping one drug is enough</span></li>
              <li><strong>The slip as written</strong><span>Matches, confidence, and one abstention</span></li>
              <li><strong>Method and evaluation</strong><span>Re-scoring, recall, and the misses</span></li>
            </ol>
          </div>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-wrap">
          <p id="ref-1" className="lp-ref">
            <sup>1</sup> van der Sijs H, Aarts J, Vulto A, Berg M. Overriding of drug safety alerts in computerized physician order
            entry. J Am Med Inform Assoc. 2006;13(2):138–147. <a href="#cite-1">Back to text</a>
          </p>
          <div className="lp-foot-row">
            <span className="lp-brand">Medsafe</span>
            <span className="meta">Prototype on a simulated dataset. No real patient data was used. A clinician decides.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
