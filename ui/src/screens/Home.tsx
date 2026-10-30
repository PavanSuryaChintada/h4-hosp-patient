// The public home page, laid out as the Round 1 landing. Every figure on it is read from the
// pipeline's data file (public/data/pipeline.json): the evaluation report, the standard-check
// reproduction, the reference-table counts and one patient the exporter chose for this page
// (demo.cards.landing). The page computes nothing; it chooses which exported values to show.

import { useEffect, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../auth';
import type { Action, Cards, EhrAlert, MedsafeAlert, PatientView, Severity } from '../data/contract';
import { ISSUE_LABEL, SEVERITY_LABEL, SEVERITY_TONE, conf, countWord, num, plural } from '../data/format';
import { useData } from '../data/load';
import { AlertGraph } from '../components/Medsafe';
import { EgfrGauge } from '../components/Charts';
import { Segmented } from '../components/ui';
import { Icon, IconTile, Meter, Units, repeat, type IconName } from '../components/viz';
import { fmtEgfr } from './PatientDetail';

type Landing = NonNullable<Cards['landing']>;
type Hero = { p: PatientView; card: Landing };

const tone = (s: Severity) => ({ ['--c' as string]: SEVERITY_TONE[s] }) as CSSProperties;
const SERIOUS: Severity[] = ['contraindicated', 'major'];
const ehrText = (a: EhrAlert) =>
  a.drugs.join(' + ') + (a.issue_type === 'renal_dose' ? ', kidney dose' : a.issue_type === 'duplicate_therapy' ? ', listed twice' : '');

const NAV: { label: string; id?: string; page?: string }[] = [
  { label: 'Problem', id: 'problem' },
  { label: 'Architecture', page: '/architecture' },
  { label: 'End to end', id: 'end-to-end' },
  { label: 'What is different', id: 'difference' },
  { label: 'Results', page: '/results' },
  { label: 'Tech stack', id: 'stack' },
  { label: 'Walkthrough', id: 'walkthrough' },
];

/** The public pages' top bar: sections of the home page, and the Results and Architecture pages. */
export function Nav() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const home = pathname === '/';
  return (
    <header className="lp-nav">
      <div className="lp-wrap lp-nav-inner">
        <Link to="/" className="lp-brand"><span className="brand-mark" aria-hidden="true" />Medsafe</Link>
        <nav aria-label="Sections" className="lp-links">
          {NAV.map((n) => n.page
            ? <NavLink key={n.label} to={n.page}>{n.label}</NavLink>
            : home ? <a key={n.label} href={`#${n.id}`}>{n.label}</a> : <Link key={n.label} to={`/#${n.id}`}>{n.label}</Link>)}
        </nav>
        <div className="lp-nav-cta">
          <span className="chip">Prototype on synthetic data</span>
          <Link to={user ? user.home : '/login'} className="btn btn-primary btn-sm">{user ? 'Open the app' : 'Sign in'}</Link>
        </div>
      </div>
    </header>
  );
}

/** One Medsafe action as a small card: the collapse with the alerts it covers, or one alert. */
function MiniAction({ act, byRank }: { act: Action; byRank: Map<number, MedsafeAlert> }) {
  if (act.kind === 'collapse') {
    const covered = act.covers.map((r) => byRank.get(r)!);
    return (
      <div className="mini-alert" style={tone(covered[0].severity)}>
        <div className="ma-top"><span className="ac-sev"><span className="sq" aria-hidden="true" />{SEVERITY_LABEL[covered[0].severity]}</span><span className="ma-act">{act.summary}</span></div>
        <div className="ma-drugs">{covered.map((a) => a.drugs.join(' + ')).join(' · ')}</div>
      </div>
    );
  }
  const a = byRank.get(act.rank)!;
  return (
    <div className="mini-alert" style={tone(a.severity)}>
      <div className="ma-top"><span className="ac-sev"><span className="sq" aria-hidden="true" />{SEVERITY_LABEL[a.severity]}</span><span className="ma-act">{a.suggested_action}</span></div>
      <div className="ma-drugs">{a.drugs.join(' + ')} · {ISSUE_LABEL[a.issue_type].toLowerCase()}</div>
    </div>
  );
}

function heroFacts({ p, card }: Hero) {
  const alerts = p.medsafe.alerts ?? [];
  const actions = p.medsafe.actions ?? [];
  const c = p.medsafe.collapse!;
  const collapse = actions.find((a): a is Extract<Action, { kind: 'collapse' }> => a.kind === 'collapse');
  const seriousEdges = c.edges.filter((e) => SERIOUS.includes(e.severity));
  return {
    alerts, actions, c, collapse,
    byRank: new Map(alerts.map((a) => [a.rank, a])),
    minor: alerts.filter((a) => !a.submitted),
    ehrRenal: p.ehr.alerts.filter((a) => a.issue_type === 'renal_dose'),
    ehrMinor: p.ehr.alerts.filter((a) => a.severity === 'minor').length,
    msRenal: alerts.filter((a) => a.issue_type === 'renal_dose'),
    serious: seriousEdges.length,
    cleared: seriousEdges.filter((e) => e.cleared).length,
    unchecked: p.medications.filter((m) => m.method === 'abstained').map((m) => m.raw),
    missed: card.missed_by_ehr,
  };
}

/* ---- hero ------------------------------------------------------------------- */

function HeroDemo({ hero }: { hero: Hero }) {
  const { p, card } = hero;
  const f = heroFacts(hero);
  const [mode, setMode] = useState<'ehr' | 'medsafe'>('ehr');
  const ehr = mode === 'ehr';
  const tiles = ehr
    ? p.ehr.alerts.map((a) => ({ color: SEVERITY_TONE[a.severity], title: ehrText(a) }))
    : [...f.actions.map((act) => {
        const a = f.byRank.get(act.kind === 'collapse' ? act.covers[0] : act.rank)!;
        return { color: SEVERITY_TONE[a.severity], title: act.kind === 'collapse' ? act.summary : a.suggested_action };
      }),
       ...repeat(f.alerts.length - f.actions.length, { color: 'var(--hairline-firm)', hollow: true, title: 'Folded into a row above, or a minor note shown last' })];
  const noise = [
    f.ehrRenal.length ? `${f.ehrRenal.length} are kidney warnings${p.egfr === null ? '' : ` at eGFR ${fmtEgfr(p.egfr)}`}` : null,
    f.ehrMinor ? `${f.ehrMinor} are minor` : null,
  ].filter(Boolean).join(' and ');

  return (
    <section className="hd" aria-label={`One patient from the training set: ${p.id}`}>
      <div className="hd-head">
        <div>
          <div className="hd-title">Patient <span className="mono">{p.id}</span></div>
          <div className="meta">
            <span className="mono">{p.age ?? '—'}</span> years, eGFR {p.egfr === null ? 'not recorded' : <span className="mono">{fmtEgfr(p.egfr)}</span>}, <span className="mono">{p.compare.medsafe.medicines}</span> medicines
          </div>
        </div>
        <Segmented label="Which check" value={mode} onChange={setMode} segments={[
          { value: 'ehr', label: `Standard check (${card.ehr_alerts})` },
          { value: 'medsafe', label: `With Medsafe (${card.actions})` },
        ]} />
      </div>

      <div className="hd-body">
        <div className="hd-graph"><AlertGraph c={f.c} width={380} height={236} removed={!ehr} unchecked={f.unchecked} /></div>
        <div className="hd-count">
          <div className={`hd-num mono${ehr ? '' : ' good'}`}>{ehr ? card.ehr_alerts : card.actions}</div>
          <div className="hd-num-label">{ehr ? 'alerts to read' : 'actions to take'}</div>
          <Units items={tiles} size={16} gap={4} columns={Math.min(tiles.length, 9)} label={ehr ? `${card.ehr_alerts} alerts` : `${card.actions} actions`} />
          <p className="hd-cap">
            {ehr
              ? <>{noise && `${noise.charAt(0).toUpperCase()}${noise.slice(1)}. `}{f.missed.length > 0 && <>Not among them: <span className="mono">{f.missed.map((l) => l.drugs.join(' + ')).join(', ')}</span>, {f.missed[0].severity}.</>}</>
              : f.c.summary}
          </p>
        </div>
      </div>

      <div className="hd-list">
        {ehr ? (
          <ul className="hd-wall">
            {p.ehr.alerts.map((a, i) => (
              <li key={i} className="wall-chip" style={tone(a.severity)}><span className="sq" aria-hidden="true" />{ehrText(a)}: {a.action ?? SEVERITY_LABEL[a.severity]}</li>
            ))}
          </ul>
        ) : (
          <div className="hd-cards">{f.actions.map((act, i) => <MiniAction key={i} act={act} byRank={f.byRank} />)}</div>
        )}
      </div>
    </section>
  );
}

function Proof({ hero }: { hero: Hero | null }) {
  const { x } = useData();
  const h = x.evaluation.report?.splits.holdout;
  if (!h) return null;
  const ours = h.official;
  const ehr = x.ehr_reference.score?.official;
  const pack = h.baselines['pack baseline'];
  const caught = h.near_misses.filter((n) => n.status === 'caught').length;
  const seeded = h.near_misses.length;
  const noiseMax = Math.max(ours.components.noise_alerts_per_patient, ehr?.components.noise_alerts_per_patient ?? 0) || 1;
  return (
    <section className="lp-proof" aria-label="Results">
      <div className="lp-wrap">
        <div className="proof-grid">
          {hero && (
            <div className="proof">
              <div className="proof-k">Patient <span className="mono">{hero.p.id}</span></div>
              <div className="proof-v mono">{hero.card.ehr_alerts} <span className="ink-3">to</span> {hero.card.actions}</div>
              <div className="proof-viz">
                <Units label={`${hero.card.ehr_alerts} alerts`} size={8} items={repeat(hero.card.ehr_alerts, { color: 'var(--ink-3)' })} />
                <span className="proof-arrow" aria-hidden="true">→</span>
                <Units label={`${hero.card.actions} actions`} size={8} items={repeat(hero.card.actions, { color: 'var(--action)' })} />
              </div>
              <p>standard-check alerts against Medsafe actions</p>
            </div>
          )}
          <div className="proof">
            <div className="proof-k">Score, organisers' evaluate.py</div>
            <div className="proof-v mono">{num(ours.primary_score, 3)}</div>
            <div className="proof-bars">
              <Meter value={ours.primary_score} width={160} height={8} color="var(--action)" label={`Medsafe ${num(ours.primary_score, 3)}`} />
              {ehr && <Meter value={ehr.primary_score} width={160} height={8} color="var(--ink-3)" label={`Standard EHR check ${num(ehr.primary_score, 3)}`} />}
            </div>
            <p>standard EHR check {ehr ? num(ehr.primary_score, 3) : '—'}, organisers' baseline {pack ? num(pack.primary_score, 3) : '—'}</p>
          </div>
          <div className="proof">
            <div className="proof-k">Near-miss recall</div>
            <div className="proof-v mono">{caught} <span className="ink-3">/</span> {seeded}</div>
            <div className="proof-viz">
              <Units label={`${caught} of ${seeded} caught`} size={8} columns={Math.min(seeded, 15)}
                items={[...repeat(caught, { color: 'var(--action)' }), ...repeat(seeded - caught, { color: 'var(--critical)', hollow: true, title: 'Missed' })]} />
            </div>
            <p>seeded hard cases still caught: misspellings, hidden combinations, eGFR at a threshold</p>
          </div>
          {ehr && (
            <div className="proof">
              <div className="proof-k">Noise alerts per patient</div>
              <div className="proof-v mono">{num(ehr.components.noise_alerts_per_patient)} <span className="ink-3">to</span> {num(ours.components.noise_alerts_per_patient)}</div>
              <div className="proof-bars">
                <Meter value={ehr.components.noise_alerts_per_patient} max={noiseMax} width={160} height={8} color="var(--ink-3)" label={`Standard EHR check ${num(ehr.components.noise_alerts_per_patient)}`} />
                <Meter value={ours.components.noise_alerts_per_patient} max={noiseMax} width={160} height={8} color="var(--action)" label={`Medsafe ${num(ours.components.noise_alerts_per_patient)}`} />
              </div>
              <p>alerts on issues that are not there or are minor: standard check against Medsafe</p>
            </div>
          )}
        </div>
        <p className="proof-note">
          <span className="mono">{h.patients}</span> training patients held out from tuning, scored by the organisers' unmodified <span className="mono">evaluate.py</span>.
          The rules' vocabulary was built on all training text, so these figures are optimistic for the hidden test set. Synthetic data, no real patients.{' '}
          <Link to="/results">Every number and the misses →</Link>
        </p>
      </div>
    </section>
  );
}

/* ---- problem illustrations -------------------------------------------------- */

const SLIP_LINES = 7;

function SlipIllustration({ p }: { p: PatientView }) {
  // Every line the standard check does not recognise, topped up with the others, in list order.
  const unknown = p.medications.filter((m) => p.ehr.matched[m.index] === null);
  const known = p.medications.filter((m) => p.ehr.matched[m.index] !== null && m.status !== 'not_a_medicine');
  const lines = [...unknown, ...known.slice(0, Math.max(0, SLIP_LINES - unknown.length))].sort((a, b) => a.index - b.index);
  return (
    <div className="ill ill-slip" aria-hidden="true">
      <div className="slip">
        <div className="slip-rx">Rx</div>
        <ol>{lines.map((m) => <li key={m.index}><span className={p.ehr.matched[m.index] === null ? 'wavy' : undefined}>{m.raw}</span></li>)}</ol>
      </div>
    </div>
  );
}

function StackIllustration({ p }: { p: PatientView }) {
  const cards = p.ehr.alerts.slice(0, 5);
  return (
    <div className="ill ill-stack" aria-hidden="true">
      <div className="stack-wrap">
        {cards.map((a, i) => (
          <div key={i} className="stack-card" style={{ ...tone(a.severity), transform: `translate(${i * 10}px, ${i * 10}px)`, zIndex: cards.length - i }}>
            <span className="sq" />{ehrText(a)}
          </div>
        ))}
        <div className="stack-badge mono">×{p.ehr.alerts.length}</div>
      </div>
    </div>
  );
}

function ContextIllustration({ pair }: { pair: NonNullable<Cards['egfr_pair']> }) {
  const { x } = useData();
  return (
    <div className="ill ill-context" aria-hidden="true">
      {[pair.low, pair.high].map((side) => (
        <div key={side.patient_id} className="ctx-row">
          <div className="ctx-top"><span>eGFR <span className="mono">{fmtEgfr(side.egfr)}</span></span><span className="ctx-flag"><Icon name="alert" size={14} />{pair.generic} kidney warning</span></div>
          <EgfrGauge value={side.egfr} stages={x.cohort.egfr_stages} width={240} />
        </div>
      ))}
      <div className="ctx-same">Same flag, same alert, two very different patients</div>
    </div>
  );
}

/* ---- architecture ----------------------------------------------------------- */

const STAGES: { icon: IconName; kicker: string; title: string; desc: string; out?: string; io?: boolean; shown?: boolean }[] = [
  { icon: 'slip', kicker: 'Input', title: 'Medication list', desc: 'As the nurse wrote it: brands, generics, misspellings, doses.', io: true },
  { icon: 'resolve', kicker: 'Step 1', title: 'Resolve names', desc: 'Exact, synonym, parts, prefix, then fuzzy. Abstain when two names are too close.', out: 'generic + confidence' },
  { icon: 'rules', kicker: 'Step 2', title: 'Check the tables', desc: 'Interactions, duplicate therapy, kidney dose, contraindications.', out: 'findings + rule id' },
  { icon: 'context', kicker: 'Step 3', title: 'Fit to the patient', desc: 'Kidney tiers read against eGFR, conditions read with their negations, stopped drugs left out.', out: 'tier + reasons' },
  { icon: 'collapse', kicker: 'Step 4', title: 'Prioritise and collapse', desc: 'Most severe first. One drug to review per cluster. Minor ones last.', out: 'actions' },
  { icon: 'screen', kicker: 'Output', title: 'Prescriber view', desc: 'Actions, the list as written, what could not be checked.', io: true, shown: true },
];

function ArchitectureGrid() {
  const { x } = useData();
  const r = x.reference;
  const seeded = x.evaluation.report?.splits.holdout?.near_misses.length;
  return (
    <figure className="arch" aria-label="Architecture: medication list to prescriber view in four steps">
      <div className="arch-grid">
        {STAGES.map((s) => (
          <div key={s.title} className={`arch-box${s.io ? ' arch-io' : ''}${s.shown ? ' arch-fixture' : ''}`}>
            <IconTile name={s.icon} tone={s.io ? 'ink' : 'action'} />
            <div className="arch-kicker">{s.kicker}</div>
            <h3>{s.title}</h3>
            <p>{s.desc}</p>
            {s.out && <span className="arch-out">{s.out}</span>}
          </div>
        ))}
        <div className="arch-feed arch-feed-ref">
          <Icon name="database" size={18} />
          <div><h4>Reference tables</h4><p><span className="mono">{r.drugs}</span> generics, <span className="mono">{r.interactions}</span> interaction pairs, <span className="mono">{r.renal_rules}</span> renal rules, <span className="mono">{r.contraindications}</span> contraindications</p></div>
        </div>
        <div className="arch-feed arch-feed-ctx">
          <Icon name="person" size={18} />
          <div><h4>Patient context</h4><p>age, weight, eGFR, conditions, pregnancy</p></div>
        </div>
        <div className="arch-feed arch-feed-eval">
          <Icon name="chart" size={18} />
          <div><h4>Evaluation harness</h4><p>the organisers' <span className="mono">evaluate.py</span>{seeded !== undefined && <>, <span className="mono">{seeded}</span> near-misses on holdout</>}</p></div>
        </div>
      </div>
      <figcaption className="arch-legend">
        <span><span className="lg lg-solid" aria-hidden="true" />Python pipeline: same input, same output, every run</span>
        <span><span className="lg lg-dashed" aria-hidden="true" />This site shows its exported output; the ward server runs it live</span>
        <Link to="/architecture">The full diagram and stack →</Link>
      </figcaption>
    </figure>
  );
}

/* ---- end to end ------------------------------------------------------------- */

function ResolveViz({ hero }: { hero: Hero }) {
  const { x, byId } = useData();
  const meds = hero.p.medications;
  // Lines that took more than an exact match first, then combination brands, then lines the standard check does not know.
  const order = [
    ...meds.filter((m) => ['fuzzy', 'prefix', 'parts', 'synonym'].includes(m.method)),
    ...meds.filter((m) => m.combination === 'brand'),
    ...meds.filter((m) => hero.p.ehr.matched[m.index] === null),
  ];
  const rows = [...new Map(order.filter((m) => m.generics.length).map((m) => [m.index, m])).values()].slice(0, 4);
  const pin = x.demo?.pins.find((p) => p.slot === 'abstention')?.patient_ids[0];
  const abstained = hero.p.medications.find((m) => m.method === 'abstained')
    ?? (pin ? byId.get(pin)?.medications.find((m) => m.method === 'abstained') : undefined);
  return (
    <div className="rv">
      {rows.map((m) => (
        <div key={m.index} className="rv-row">
          <span className="raw-chip mono" title={m.raw}>"{m.raw}"</span>
          <span className="rv-arrow" aria-hidden="true">→</span>
          <span className="res-chip">{m.generics.join(' + ')}</span>
          <Meter value={m.confidence} width={96} height={6} />
          <span className="mono">{conf(m.confidence)}</span>
        </div>
      ))}
      {abstained && (
        <div className="rv-row rv-abst">
          <span className="raw-chip mono" title={abstained.raw}>"{abstained.raw}"</span>
          <span className="rv-arrow" aria-hidden="true">→</span>
          <div className="rv-cands">
            {abstained.candidates.map(([g, s]) => (
              <div key={g} className="rv-cand"><span>{g}</span><Meter value={s} width={96} height={6} color="var(--warn)" /><span className="mono">{conf(s)}</span></div>
            ))}
          </div>
          <span className="tag tag-warn">too close: verify manually{pin && !hero.p.medications.includes(abstained) ? `, patient ${pin}` : ''}</span>
        </div>
      )}
    </div>
  );
}

const ISSUES = ['interaction', 'duplicate_therapy', 'renal_dose', 'contraindication'] as const;
const LEVELS: Severity[] = ['contraindicated', 'major', 'moderate', 'minor'];

function FindingsViz({ hero }: { hero: Hero }) {
  const { alerts } = heroFacts(hero);
  return (
    <div className="fv">
      <div className="fv-groups">
        {ISSUES.map((t) => {
          const items = alerts.filter((a) => a.issue_type === t);
          return (
            <div key={t} className="fv-group">
              <Units label={`${ISSUE_LABEL[t]}: ${items.length}`} size={28} gap={6} items={items.map((a) => ({ color: SEVERITY_TONE[a.severity], title: `${a.drugs.join(' + ')}: ${a.suggested_action}` }))} />
              <div className="fv-label">{ISSUE_LABEL[t]} <span className="mono">{items.length}</span></div>
            </div>
          );
        })}
      </div>
      <div className="fv-legend">
        {LEVELS.map((s) => (
          <span key={s}><span className="sw" style={{ background: SEVERITY_TONE[s] }} />{SEVERITY_LABEL[s]} <span className="mono">{alerts.filter((a) => a.severity === s).length}</span></span>
        ))}
        <span className="fv-total">{plural(alerts.length, 'finding')}</span>
      </div>
    </div>
  );
}

function FitViz({ hero }: { hero: Hero }) {
  const { x } = useData();
  const { p } = hero;
  const f = heroFacts(hero);
  return (
    <div className="sv">
      <div className="sv-lanes sv-lanes-2">
        <div className="sv-lane" style={{ ['--c' as string]: 'var(--ink-3)' } as CSSProperties}>
          <div className="sv-lane-head"><span className="sq" />Standard check: eGFR not read</div>
          {f.ehrRenal.map((a, i) => <div key={i} className="sv-chip ghost">{a.drugs.join(' + ')}<span>{SEVERITY_LABEL[a.severity]} kidney warning, whatever the eGFR</span></div>)}
          {f.ehrRenal.length === 0 && <div className="sv-chip ghost">No kidney warning<span>on the names it knows</span></div>}
        </div>
        <div className="sv-lane" style={{ ['--c' as string]: 'var(--action)' } as CSSProperties}>
          <div className="sv-lane-head"><span className="sq" />Medsafe at eGFR {p.egfr === null ? 'not recorded' : fmtEgfr(p.egfr)}</div>
          {f.msRenal.map((a) => <div key={a.rank} className="sv-chip">{a.drugs.join(' + ')}<span>{SEVERITY_LABEL[a.severity]}: {a.suggested_action}</span></div>)}
          {f.msRenal.length === 0 && <div className="sv-chip sv-ok">No kidney-dose alert<span>Each drug's tiers in the renal table were read against this eGFR; none applies.</span></div>}
        </div>
      </div>
      {p.egfr !== null && (
        <div className="sv-why">
          <span>eGFR <span className="mono">{fmtEgfr(p.egfr)}</span>, KDIGO category <span className="mono">{p.compare.medsafe.egfr_stage}</span> (display only)</span>
          <EgfrGauge value={p.egfr} stages={x.cohort.egfr_stages} width={320} />
        </div>
      )}
    </div>
  );
}

function CollapseViz({ hero }: { hero: Hero }) {
  const f = heroFacts(hero);
  return (
    <div className="cv">
      <div className="cv-pair">
        <div><div className="cv-label">Before: <span className="mono">{f.serious}</span> serious interactions</div><AlertGraph c={f.c} width={300} height={200} unchecked={f.unchecked} /></div>
        <div><div className="cv-label">After reviewing {f.c.chosen.join(' and ')}: <span className="mono">{f.serious - f.cleared}</span> left</div><AlertGraph c={f.c} width={300} height={200} removed unchecked={f.unchecked} /></div>
      </div>
    </div>
  );
}

function OutputViz({ hero }: { hero: Hero }) {
  const f = heroFacts(hero);
  return (
    <div className="ov">
      {f.actions.map((act, i) => <MiniAction key={i} act={act} byRank={f.byRank} />)}
      {f.minor.length > 0 && <p className="meta">{plural(f.minor.length, 'minor finding')}, shown last and not sent as an alert.</p>}
    </div>
  );
}

function e2eSteps(hero: Hero, pair: Cards['egfr_pair'], pairAction: string | undefined) {
  const { p, card } = hero;
  const f = heroFacts(hero);
  const m = p.compare.medsafe;
  return [
    { icon: 'resolve' as IconName, title: 'Read as written', Viz: ResolveViz,
      text: `${m.checked} of ${m.lines} lines resolve to a generic with a confidence, and ${plural(m.combinations_expanded, 'combination brand')} open into their parts. The standard check recognises ${m.lines - p.compare.ehr.not_in_formulary} of them. A name too close to two candidates goes to a manual check instead of a guess.` },
    { icon: 'rules' as IconName, title: 'Check the tables', Viz: FindingsViz,
      text: `Every pair and every drug against the pack's tables: ${plural(f.alerts.length, 'finding')}, each with its rule id and the table's own severity and action. The standard check raised ${card.ehr_alerts}, on the names it knows.` },
    { icon: 'context' as IconName, title: 'Fit to the patient', Viz: FitViz,
      text: `The standard check fires a kidney warning for ${f.ehrRenal.length ? f.ehrRenal.map((a) => a.drugs.join(' + ')).join(', ') : 'none of these drugs'} whatever the eGFR. Medsafe reads this patient's eGFR against each drug's tiers and raises ${f.msRenal.length || 'none'}.${pair && pairAction ? ` On another patient, ${pair.generic} at eGFR ${fmtEgfr(pair.low.egfr)}, the same tiers say: "${pairAction}".` : ''}` },
    { icon: 'collapse' as IconName, title: 'Collapse', Viz: CollapseViz,
      text: `${f.c.summary ?? ''} Medsafe names the drug to review; it does not stop anything on its own.` },
    { icon: 'screen' as IconName, title: 'Show the prescriber', Viz: OutputViz,
      text: `${plural(card.actions, 'action')} instead of ${card.ehr_alerts} alerts, each with the rule behind it, its confidence and what could not be checked. A clinician decides.` },
  ];
}

function EndToEnd({ hero }: { hero: Hero }) {
  const { x, byId } = useData();
  const pair = x.demo?.cards.egfr_pair ?? null;
  const low = pair && pair.low.medsafe_alert !== null ? byId.get(pair.low.patient_id)?.medsafe.alerts?.[pair.low.medsafe_alert] : undefined;
  const steps = e2eSteps(hero, pair, low?.suggested_action);
  const [i, setI] = useState(0);
  const step = steps[i];
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight') setI((v) => Math.min(steps.length - 1, v + 1));
    if (e.key === 'ArrowLeft') setI((v) => Math.max(0, v - 1));
  };
  return (
    <div className="e2e">
      <div className="e2e-tabs" role="tablist" aria-label="End-to-end steps" onKeyDown={onKey}>
        {steps.map((s, n) => (
          <button key={s.title} type="button" role="tab" id={`e2e-tab-${n}`} aria-selected={n === i} aria-controls="e2e-panel"
            tabIndex={n === i ? 0 : -1} className={`e2e-tab${n === i ? ' on' : ''}${n < i ? ' done' : ''}`} onClick={() => setI(n)}>
            <span className="e2e-tab-n mono">{n + 1}</span>
            <Icon name={s.icon} size={18} />
            <span className="e2e-tab-t">{s.title}</span>
          </button>
        ))}
      </div>
      <div className="e2e-panel" role="tabpanel" id="e2e-panel" aria-labelledby={`e2e-tab-${i}`}>
        <div className="e2e-text">
          <h3>{step.title}</h3>
          <p>{step.text}</p>
          <div className="e2e-nav">
            {i > 0 && <button type="button" className="btn btn-secondary btn-sm" onClick={() => setI(i - 1)}>Previous step</button>}
            {i < steps.length - 1 && <button type="button" className="btn btn-primary btn-sm" onClick={() => setI(i + 1)}>Next step</button>}
          </div>
        </div>
        <div className="e2e-viz"><step.Viz hero={hero} /></div>
      </div>
    </div>
  );
}

/* ---- difference ------------------------------------------------------------- */

function Compare({ hero }: { hero: Hero }) {
  const { p, card } = hero;
  const f = heroFacts(hero);
  const folded = f.collapse?.covers.length ?? 0;
  return (
    <div className="cmp">
      <figure className="cmp-col">
        <figcaption><Icon name="alert" size={16} />Standard EHR check</figcaption>
        <div className="mock mock-them" aria-hidden="true">
          <div className="mock-bar">Drug interaction warnings <span className="mono">{card.ehr_alerts}</span></div>
          <ul>
            {p.ehr.alerts.map((a, i) => (
              <li key={i}><Icon name="alert" size={12} /><span>{ehrText(a)}</span><span className="mock-btn">Override</span></li>
            ))}
          </ul>
          <div className="mock-foot"><span className="mock-btn">Override all</span></div>
        </div>
        <p>
          Every pair at the table's severity and a kidney warning per drug, whatever the eGFR. {p.compare.ehr.not_in_formulary} of {p.compare.medsafe.lines} lines
          are names it does not know, so they are never checked{f.missed.length > 0 && <>: it misses <span className="mono">{f.missed.map((l) => l.drugs.join(' + ')).join(', ')}</span></>}.
        </p>
      </figure>
      <figure className="cmp-col cmp-us">
        <figcaption><Icon name="check" size={16} />Medsafe</figcaption>
        <div className="mock mock-us" aria-hidden="true">
          <div className="mock-bar">Patient {p.id} <span className="mono">{card.actions}</span></div>
          <div className="mock-cards">{f.actions.map((act, i) => <MiniAction key={i} act={act} byRank={f.byRank} />)}</div>
          <div className="mock-folded">
            {folded > 0 && <div><Units label="Folded" size={8} gap={2} items={repeat(folded, { color: 'var(--critical)', hollow: true })} />{folded} alerts folded into the {f.c.chosen.join(' and ')} row</div>}
            {f.minor.length > 0 && <div><Units label="Minor" size={8} gap={2} items={repeat(f.minor.length, { color: 'var(--ink-3)', hollow: true })} />{plural(f.minor.length, 'minor finding')}, shown last</div>}
          </div>
          <div className="mock-foot">Checked {p.compare.medsafe.checked} of {p.compare.medsafe.lines} lines. A clinician decides.</div>
        </div>
        <p>One decision per cluster, the most serious first, with the rule behind every action. It raised {card.serious_medsafe} of the {card.serious_labelled} serious labelled issues; the standard check raised {card.serious_ehr}.</p>
      </figure>
    </div>
  );
}

const CONTRAST: { icon: IconName; aspect: string; them: string; us: string }[] = [
  { icon: 'slip', aspect: 'Input', them: 'Names in its formulary only', us: 'The list as written' },
  { icon: 'question', aspect: 'Unclear names', them: 'Skipped without a word', us: 'Abstains and asks for a check' },
  { icon: 'context', aspect: 'Kidney function', them: 'The same warning at any eGFR', us: 'Each drug\'s tiers, read against this eGFR' },
  { icon: 'collapse', aspect: 'Output', them: 'One alert per pair', us: 'Most serious first, one drug to review per cluster' },
  { icon: 'shield', aspect: 'Nothing found', them: '"No interactions"', us: '"No issue found in what was seen"' },
  { icon: 'chart', aspect: 'Evaluation', them: 'Alert counts, if anything', us: 'The organisers\' evaluate.py, misses listed' },
];

/* ---- page ------------------------------------------------------------------- */

const STACK: [string, string, string, string][] = [
  ['Py', 'Python', '3.11', 'The engine, the exporter and the ward server'],
  ['RF', 'rapidfuzz', '3.14', 'Fuzzy name matching: the one dependency on the scoring path'],
  ['R', 'React', '18.3', 'Screens and state'],
  ['TS', 'TypeScript', '5.6 strict', 'The typed contract with the pipeline\'s output'],
  ['V', 'Vite', '5.4', 'Dev server and production build'],
  ['SVG', 'Hand-written SVG', 'no library', 'Graph, charts and diagrams'],
];

const SHIP: [IconName, string, string][] = [
  ['commit', 'Push to main', 'GitHub'],
  ['box', 'Strict build', 'npm ci, tsc, Vite'],
  ['globe', 'Static hosting', 'GitHub Pages and Vercel'],
  ['browser', 'Runs in the browser', 'Reads the pipeline\'s exported file'],
];

const WARD: [IconName, string, string][] = [
  ['person', 'Nurse', 'Admits the patient, pulls records through ABHA with consent (a simulated sandbox here), adds what they brought.'],
  ['chart', 'Lab technician', 'Enters eGFR. The kidney-dose rules re-run on it.'],
  ['question', 'Pharmacist', 'Confirms the names the system would not guess, answers deferred alerts.'],
  ['check', 'Prescriber', 'Accepts, overrides with a reason, or defers each alert.'],
  ['lock', 'Audit log', 'Every entry and decision, with who and when.'],
];

export function Home() {
  const { user } = useAuth();
  const { x, byId } = useData();
  const { hash } = useLocation();
  useEffect(() => { if (hash) document.getElementById(hash.slice(1))?.scrollIntoView(); }, [hash]);

  const card = x.demo?.cards.landing ?? null;
  const hp = card ? byId.get(card.patient_id) : undefined;
  const hero: Hero | null = card && hp?.medsafe.collapse ? { p: hp, card } : null;
  const pair = x.demo?.cards.egfr_pair ?? null;
  const pairLow = pair && pair.low.medsafe_alert !== null ? byId.get(pair.low.patient_id)?.medsafe.alerts?.[pair.low.medsafe_alert] : undefined;
  const ruleId = hero?.p.medsafe.alerts?.[0]?.rule_id;
  const demoHref = user ? user.home : '/login';
  const f = hero ? heroFacts(hero) : null;

  const WALK: [IconName, string, string, string][] = [
    ['queue', 'The queue', 'Every patient, most urgent first', '/app?demo=1'],
    ...(hero ? [
      ['person', `Patient ${hero.p.id}`, `${hero.p.age ?? '—'} years, ${hero.p.compare.medsafe.medicines} medicines, the standard check first`, `/app/patient/${hero.p.id}?mode=ehr`],
      ['toggle', 'The switch', `${hero.card.ehr_alerts} alerts to ${plural(hero.card.actions, 'action')}, in one click`, `/app/patient/${hero.p.id}`],
    ] as [IconName, string, string, string][] : []),
    ['graph', 'Why it matters', 'Four ways a standard check fails', '/app/why'],
    ['slip', 'The list as written', 'Matches, confidence, the lines it would not guess', '/app/resolution'],
    ['chart', 'Results', 'Scores, misses and the model graphs', '/results'],
  ];

  return (
    <div className="lp">
      <Nav />

      <main>
        <section className="lp-hero">
          <div className="lp-wrap lp-hero-grid">
            <div className="lp-hero-copy">
              <p className="lp-kicker">Medication safety, a second pair of eyes</p>
              {hero
                ? <h1 className="lp-h1"><span>{countWord(hero.card.ehr_alerts)} warnings.</span> <span>{countWord(hero.card.actions)} decision{hero.card.actions === 1 ? '' : 's'}.</span></h1>
                : <h1 className="lp-h1"><span>Every alert earns its place.</span></h1>}
              <p className="lp-lead">
                Medsafe reads a medication list the way it was written, checks it against the reference tables for the patient in front of you,
                and turns each cluster of alerts into the one drug to review first.
              </p>
              <div className="lp-ctas">
                <Link to={demoHref} className="btn btn-primary">Open the live demo</Link>
                <a href="#walkthrough" className="btn btn-secondary">Take the guided walkthrough</a>
              </div>
              <ul className="hero-points">
                <li><Icon name="slip" size={16} />Reads brands, generics and misspellings</li>
                <li><Icon name="context" size={16} />Reads eGFR against each drug's kidney tiers</li>
                <li><Icon name="collapse" size={16} />One drug to review per cluster, serious first</li>
              </ul>
            </div>
            {hero && <HeroDemo hero={hero} />}
          </div>
        </section>

        <Proof hero={hero} />

        <section id="problem" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">The warning that matters gets lost among the ones that do not.</h2>
            <p className="lp-lead lp-measure">
              Clinicians override 49% to 96% of drug-safety alerts in computerised order entry.<sup><a href="#ref-1" id="cite-1">1</a></sup> Three
              things cause it, and Medsafe answers each one.
            </p>
            <div className="lp-three">
              {hero && f && (
                <article className="ill-card"><SlipIllustration p={hero.p} />
                  <h3 className="lp-h3">Lists are messy</h3>
                  <p>Brands, generics, misspellings and doses on one list. Patient <span className="mono">{hero.p.id}</span> has {hero.p.compare.medsafe.lines} lines; the standard check does not recognise the {hero.p.compare.ehr.not_in_formulary} underlined, so it never checks them.</p>
                </article>
              )}
              {hero && f && (
                <article className="ill-card"><StackIllustration p={hero.p} />
                  <h3 className="lp-h3">One alert per pair</h3>
                  <p>{hero.p.compare.medsafe.medicines} medicines raise {hero.card.ehr_alerts} warnings.{f.ehrRenal.length > 0 && hero.p.egfr !== null && <> {f.ehrRenal.length} are kidney warnings at eGFR {fmtEgfr(hero.p.egfr)}.</>}{f.missed.length > 0 && <> The {f.missed.length} {f.missed[0].severity} pairs on the list are not among them.</>}</p>
                </article>
              )}
              {pair && (
                <article className="ill-card"><ContextIllustration pair={pair} />
                  <h3 className="lp-h3">Context is ignored</h3>
                  <p>
                    The {pair.generic} kidney warning fires the same way at eGFR {fmtEgfr(pair.low.egfr)} and {fmtEgfr(pair.high.egfr)}.
                    {pairLow && <> At {fmtEgfr(pair.low.egfr)} Medsafe raises it as {pairLow.severity}: "{pairLow.suggested_action}".</>}
                    {pair.high.medsafe_alert === null && <> At {fmtEgfr(pair.high.egfr)} it raises nothing.</>}
                  </p>
                </article>
              )}
            </div>
          </div>
        </section>

        <section id="architecture" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <h2 className="lp-h2">Four steps between the list and the screen.</h2>
            <p className="lp-lead lp-measure">
              Every step records why it decided what it did. No model writes an action: each one traces back to a rule id
              {ruleId ? <> such as <span className="mono">{ruleId}</span></> : null}.
            </p>
            <ArchitectureGrid />
          </div>
        </section>

        {hero && (
          <section id="end-to-end" className="lp-section">
            <div className="lp-wrap">
              <h2 className="lp-h2">One list, end to end.</h2>
              <p className="lp-lead lp-measure">
                Patient <span className="mono">{hero.p.id}</span>: {hero.p.age ?? '—'} years old, eGFR {hero.p.egfr === null ? 'not recorded' : fmtEgfr(hero.p.egfr)}, {hero.p.compare.medsafe.medicines} medicines.
                Step through what the pipeline computed for this list.
              </p>
              <EndToEnd hero={hero} />
            </div>
          </section>
        )}

        <section id="difference" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <h2 className="lp-h2">The same list, two screens.</h2>
            {hero && <Compare hero={hero} />}
            <div className="contrast-grid">
              {CONTRAST.map((c) => (
                <div key={c.aspect} className="contrast">
                  <IconTile name={c.icon} size={32} />
                  <div>
                    <h3 className="lp-h3">{c.aspect}</h3>
                    <p className="contrast-them"><span aria-hidden="true">×</span> {c.them}</p>
                    <p className="contrast-us"><Icon name="check" size={14} /> {c.us}</p>
                  </div>
                </div>
              ))}
            </div>

            <div id="honesty" className="lp-three lp-trust">
              <article className="lp-trust-card"><IconTile name="shield" tone="ok" /><h3 className="lp-h3">Says what it could not check</h3><p>With nothing found it says no issue was found in what was seen, names every line and value it could not check, and leaves the decision with the clinician.</p></article>
              <article className="lp-trust-card"><IconTile name="question" tone="warn" /><h3 className="lp-h3">Abstains instead of guessing</h3><p>A name too close to two candidates is marked "verify manually" and kept out of the checks, so a wrong match cannot hide a real interaction.</p></article>
              <article className="lp-trust-card"><IconTile name="flag" tone="critical" /><h3 className="lp-h3">Reports its caveats</h3><p>Synthetic data, simplified tables, a sandbox for ABHA, and holdout figures that are optimistic for the hidden set: each is stated where it applies.</p></article>
            </div>
          </div>
        </section>

        <section id="ward" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">On a ward, end to end.</h2>
            <p className="lp-lead lp-measure">Five roles, one list. Every check runs the real pipeline on the ward server, which runs locally with <span className="mono">python tools/serve_ui.py</span>.</p>
            <ol className="ship ship-5">
              {WARD.map(([icon, t, s]) => (
                <li key={t}><IconTile name={icon} size={36} /><div><strong>{t}</strong><p>{s}</p></div></li>
              ))}
            </ol>
          </div>
        </section>

        <section id="stack" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <h2 className="lp-h2">A small stack, on purpose.</h2>
            <p className="lp-lead lp-measure">No language model, no network at runtime, no database on the scoring path. The same list gives the same alerts every run.</p>
            <div className="stack-grid">
              {STACK.map(([m, n, v, why]) => (
                <div key={n} className="stack-item">
                  <span className="mono-tile mono">{m}</span>
                  <div><div className="stack-name">{n} <span className="mono ink-3">{v}</span></div><p>{why}</p></div>
                </div>
              ))}
            </div>

            <h3 className="lp-h3 lp-sub">How it ships</h3>
            <ol className="ship">
              {SHIP.map(([icon, t, s]) => (
                <li key={t}><IconTile name={icon} size={36} /><div><strong>{t}</strong><p>{s}</p></div></li>
              ))}
            </ol>

            <h3 className="lp-h3 lp-sub">Next, not built yet</h3>
            <ul className="next-list">
              <li>A live ABDM connection in place of the ABHA sandbox, with the same consent step.</li>
              <li>Licensed drug reference data in place of the challenge's simplified tables.</li>
              <li>Hospital record integration through HL7 FHIR medication requests.</li>
              <li>Prospective evaluation against near-misses labelled by pharmacists.</li>
            </ul>
          </div>
        </section>

        <section id="walkthrough" className="lp-section">
          <div className="lp-wrap">
            <div className="walk-head">
              <div>
                <h2 className="lp-h2">See it in two minutes.</h2>
                <p className="lp-lead">Sign in with a demo account and follow these screens in order. Demo mode pins the patients this page talks about.</p>
              </div>
              <div className="lp-ctas">
                <Link to={user ? '/app?demo=1' : '/login'} className="btn btn-primary">Start the walkthrough</Link>
                <Link to={demoHref} className="btn btn-secondary">Explore on my own</Link>
              </div>
            </div>
            <ol className="walk-strip">
              {WALK.map(([icon, t, s, to], n) => (
                <li key={t}>
                  <Link to={to} className="walk-link">
                    <div className="walk-top"><span className="mono">{n + 1}</span><IconTile name={icon} size={32} /></div>
                    <strong>{t}</strong>
                    <span>{s}</span>
                  </Link>
                </li>
              ))}
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
            <span className="lp-brand"><span className="brand-mark" aria-hidden="true" />Medsafe</span>
            <span className="meta">Prototype on the synthetic H4 dataset ({plural(x.source.patients, 'training patient')} shown). Drug facts are simplified for the challenge. No real patient data. A clinician decides.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
