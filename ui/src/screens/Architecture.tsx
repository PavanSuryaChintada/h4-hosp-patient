// What Medsafe is built from (public), and the trained-model graphs shown on the Results page.
// The figures are PNGs drawn by eval/ml_plots.py from the newest ml-challenger report; their
// captions' numbers are read from the same report through pipeline.json.

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { num } from '../data/format';
import { useData } from '../data/load';
import { Architecture } from '../components/Architecture';
import { Nav } from './Home';

const fig = (name: string) => `${import.meta.env.BASE_URL}figures/${name}`;

const STACK: [string, string, string][] = [
  ['Engine language', 'Python 3.11', 'The organisers\' evaluate.py is Python; the engine stays in its world.'],
  ['Engine libraries', 'Standard library + rapidfuzz', 'csv and json for reading, rapidfuzz for fuzzy name matching. Nothing else on the scoring path.'],
  ['Name reading', 'Normalise, exact, synonym, parts, prefix, fuzzy (OSA edits), abstain', 'A name too close to call becomes "verify manually", never a guess.'],
  ['Checks', 'Interactions, duplicate therapy, renal tiers, contraindications', 'Each from the pack\'s reference tables, at the table\'s own severity and action.'],
  ['Clinician layer', 'Prioritise, collapse, roles, permissions, override reasons, audit log', 'src/medsafe/explain/prioritise.py and src/medsafe/workflow.py; outside the submission track.'],
  ['Ward server', 'Python http.server (tools/serve_ui.py)', 'Runs the same pipeline on each patient entered by hand. Local only.'],
  ['Web app', 'React 18, TypeScript, Vite, React Router', 'Charts and diagrams are hand-written SVG. IBM Plex Sans and Mono.'],
  ['Hosting', 'GitHub Pages and Vercel', 'Static: the app reads one exported data file and computes nothing.'],
  ['Evaluation', 'The organisers\' evaluate.py, a fixed dev / holdout split', 'Plus a reproduction of a standard EHR check scored the same way.'],
  ['Experiments', 'n-gram TF-IDF nearest neighbour, logistic regression, gradient-boosted trees', 'Written in the standard library, trained on dev, scored on holdout. Graphs with matplotlib.'],
  ['Tests', 'pytest', 'Including guards: nothing on the scoring path reads the labels, opens the network or calls a model.'],
];

const NOT_USED: [string, string][] = [
  ['A language model', 'Rule 1: deterministic rules only. Same input, same output, every run.'],
  ['Network calls at runtime', 'The zip runs offline on the grader\'s machine.'],
  ['A model in the submission', 'Three were trained and measured; the rules held on every comparison.'],
  ['Real patient data', 'The H4 pack is synthetic. The ABHA step is a labelled sandbox.'],
];

function Figure({ name, title, children }: { name: string; title: string; children: ReactNode }) {
  return (
    <figure className="model-fig">
      <h3 className="lp-h3">{title}</h3>
      <img src={fig(name)} alt={title} loading="lazy" />
      <figcaption>{children}</figcaption>
    </figure>
  );
}

/** The five graphs from eval/ml_plots.py, with captions from the exported report. */
export function ModelFigures() {
  const { x } = useData();
  const c = x.ml_challenger;
  if (!c) return null;
  const ml = c.names.submissions['ML challenger'], rules = c.names.submissions['rules (shipped)'];
  const d = c.conditions, t = c.triage;
  return (
    <section className="results-figs" aria-label="Graphs of the trained models">
      <h2 className="section" style={{ marginTop: 48 }}>The graphs</h2>
      <p className="meta">Drawn by <span className="mono">python -m eval.ml_plots</span> from <span className="mono">{c.path}</span> and the pack's own files.</p>
      <div className="model-figs">
        <Figure name="2_scores.png" title="Every model against the rules">
          Rules {num(rules.primary_score, 3)} against {num(ml.primary_score, 3)} for the name matcher and {num(d.official['learned reader'].primary_score, 3)} for the condition reader.
          Triage lifts a standard EHR check from {num(t.official['standard check'].primary_score, 3)} to {num(t.official['standard check + learned triage'].primary_score, 3)}.
        </Figure>
        <Figure name="1_dataset.png" title="The data we were given">
          The organisers' training patients with their labelled issues, the hidden test patients, and how each written line is spelled.
        </Figure>
        <Figure name="3_names.png" title="Model 1: reading drug names">
          Character n-gram TF-IDF with nearest neighbours. {ml.lines.wrong_confident} holdout names confidently wrong against {rules.lines.wrong_confident} for the rules;
          misspelled lines {num(ml.lines.misspelled_accuracy, 3)} against {num(rules.lines.misspelled_accuracy, 3)}.
        </Figure>
        <Figure name="4_conditions.png" title="Model 2: reading conditions and negation">
          Logistic regression, trained on {d.examples.toLocaleString('en-GB')} (patient, condition) pairs of which only {d.present} were present.
          Serious contraindications caught: {num(d.official['learned reader'].contraindication.serious_recall)} against {num(d.official['rules (shipped)'].contraindication.serious_recall)}.
        </Figure>
        <Figure name="5_triage.png" title="Model 3: which alerts are worth showing">
          Gradient-boosted trees, ranking AUC {num(t.holdout_auc, 3)}. They held back {t.held_back} of {t.holdout_alerts} standard-check alerts, {t.held_back_worth_showing} of them real,
          and split most on {t.importance.slice(0, 2).map(([f]) => f).join(' and ')}.
        </Figure>
      </div>
    </section>
  );
}

export function ArchitecturePage() {
  return (
    <div className="home">
      <Nav />
      <section className="home-section">
        <div className="home-wrap">
          <p className="lp-kicker">Architecture</p>
          <h1 className="home-h2">What Medsafe is built from.</h1>
          <p className="home-lead home-measure">
            One deterministic engine in Python. The same code writes the submission files and serves the ward; everything a clinician sees is a second
            track on top of it. The experiments sit beside it and never touch what is submitted.
          </p>
          <Architecture />
        </div>
      </section>

      <section className="home-section home-alt">
        <div className="home-wrap">
          <h2 className="home-h2">Exactly what we used.</h2>
          <div className="panel arch-table">
            <table className="t">
              <colgroup><col style={{ width: 180 }} /><col style={{ width: 360 }} /><col /></colgroup>
              <thead><tr><th>Part</th><th>What</th><th>Why</th></tr></thead>
              <tbody>
                {STACK.map(([part, what, why]) => (
                  <tr key={part}><th scope="row">{part}</th><td>{what}</td><td className="ink-2">{why}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3 className="lp-h3" style={{ marginTop: 32 }}>What we deliberately did not use</h3>
          <div className="home-three" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', marginTop: 16 }}>
            {NOT_USED.map(([what, why]) => <article key={what} className="home-card"><h3 className="lp-h3">{what}</h3><p>{why}</p></article>)}
          </div>
          <p className="home-note">How the trained models did, with every graph: <Link to="/results">Results →</Link></p>
        </div>
      </section>
    </div>
  );
}
