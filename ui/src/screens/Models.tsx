// What Medsafe is built from, and the three trained models measured against its rules. The
// figures are PNGs drawn by eval/ml_plots.py from the newest eval/ml_challenger report; the
// captions' numbers are read from the same report through pipeline.json.

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { num } from '../data/format';
import { useData } from '../data/load';
import { Architecture } from '../components/Architecture';
import { Nav } from './Home';

const fig = (name: string) => `${import.meta.env.BASE_URL}figures/${name}`;

function Figure({ name, title, children }: { name: string; title: string; children: ReactNode }) {
  return (
    <figure className="model-fig">
      <h3 className="lp-h3">{title}</h3>
      <img src={fig(name)} alt={title} loading="lazy" />
      <figcaption>{children}</figcaption>
    </figure>
  );
}

export function Models() {
  const { x } = useData();
  const c = x.ml_challenger;
  const names = c?.names.submissions;
  const ml = names?.['ML challenger'];
  const rules = names?.['rules (shipped)'];
  const t = c?.triage;
  const d = c?.conditions;
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
          <p className="lp-kicker">Trained models</p>
          <h2 className="home-h2">Three models, measured against the rules.</h2>
          <p className="home-lead home-measure">
            Each is trained on the dev split only, in the standard library, and scored once on the holdout split by the organisers' <span className="mono">evaluate.py</span>,
            through the same rule engine. None is a language model, and none is on the submission path. The rules' perfect holdout rows are optimistic: their vocabulary was
            built on all training text.
          </p>
          {!c ? <p className="empty">Run <span className="mono">python -m eval.ml_challenger</span> and <span className="mono">python -m eval.ml_plots</span> to draw these.</p> : (
            <div className="model-figs">
              <Figure name="2_scores.png" title="Every model against the rules">
                Rules {num(rules!.primary_score, 3)} against {num(ml!.primary_score, 3)} for the name matcher and {num(d!.official['learned reader'].primary_score, 3)} for the condition reader.
                Triage lifts a standard EHR check from {num(t!.official['standard check'].primary_score, 3)} to {num(t!.official['standard check + learned triage'].primary_score, 3)}.
              </Figure>
              <Figure name="1_dataset.png" title="The data we were given">
                The organisers' training patients with their labelled issues, the hidden test patients, and how each written line is spelled.
              </Figure>
              <Figure name="3_names.png" title="Model 1: reading drug names">
                Character n-gram TF-IDF with nearest neighbours. {ml!.lines.wrong_confident} holdout names confidently wrong against {rules!.lines.wrong_confident} for the rules;
                misspelled lines {num(ml!.lines.misspelled_accuracy, 3)} against {num(rules!.lines.misspelled_accuracy, 3)}.
              </Figure>
              <Figure name="4_conditions.png" title="Model 2: reading conditions and negation">
                Logistic regression, trained on {d!.examples.toLocaleString('en-GB')} (patient, condition) pairs of which only {d!.present} were present.
                Serious contraindications caught: {num(d!.official['learned reader'].contraindication.serious_recall)} against {num(d!.official['rules (shipped)'].contraindication.serious_recall)}.
              </Figure>
              <Figure name="5_triage.png" title="Model 3: which alerts are worth showing">
                Gradient-boosted trees, ranking AUC {num(t!.holdout_auc, 3)}. They held back {t!.held_back} of {t!.holdout_alerts} standard-check alerts, {t!.held_back_worth_showing} of them real,
                and split most on {t!.importance.slice(0, 2).map(([f]) => f).join(' and ')}.
              </Figure>
            </div>
          )}
          <p className="home-note">Redraw with <span className="mono">python -m eval.ml_challenger</span> then <span className="mono">python -m eval.ml_plots</span>. Report <span className="mono">{c?.path}</span>. <Link to="/app/evaluation">Full evaluation →</Link></p>
        </div>
      </section>
    </div>
  );
}
