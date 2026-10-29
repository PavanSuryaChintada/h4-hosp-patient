import { useState, type CSSProperties, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth';
import { DRUGS, EXPANDED_PAIR_COUNT, INTERACTIONS } from '../data/drugs';
import { BY_ID, METRICS, name, type Alert } from '../data/engine';
import { NEAR_MISS } from '../data/evaluation';
import { HERO_ID } from '../data/patients';
import { AlertGraph } from '../components/AlertGraph';
import { AlertCard } from '../components/AlertCard';
import { Segmented } from '../components/ui';
import { EgfrGauge, Icon, IconTile, Meter, SEV_COLOR, Units, repeat, type IconName } from '../components/viz';

const hero = BY_ID[HERO_ID];
const anchor = hero.anchors[0];
const about = hero.all.filter((a) => a.drugs.includes(anchor)).length;
const lows = hero.all.filter((a) => a.severity === 'low').length;
const SEV_LABEL = { high: 'High', medium: 'Medium', low: 'Low' };
const DEFAULT_SEV: Record<string, string> = { major: 'high', moderate: 'medium', minor: 'low' };
const res = METRICS.resolution;
const resolutionPct = Math.round((res.fuzzyCorrect / res.fuzzy) * 100);
const sevVar = (a: Alert) => ({ ['--c' as string]: SEV_COLOR[a.severity] }) as CSSProperties;
const shownKeys = new Set(hero.collapsed.map((a) => a.key));
const folded = hero.all.filter((a) => !shownKeys.has(a.key) && a.severity !== 'low');
const findingLabel = (a: Alert) =>
  [...new Set(a.drugs)].map(name).join(' + ') + (a.kind === 'renal' ? ', renal dose' : a.kind === 'duplicate' ? ', listed twice' : '');

const NAV = [
  { href: '#problem', label: 'Problem' },
  { href: '#architecture', label: 'Architecture' },
  { href: '#end-to-end', label: 'End to end' },
  { href: '#difference', label: 'What is different' },
  { href: '#stack', label: 'Tech stack' },
  { href: '#walkthrough', label: 'Walkthrough' },
];

function MiniAlert({ a }: { a: Alert }) {
  return (
    <div className="mini-alert" style={sevVar(a)}>
      <div className="ma-top">
        <span className="ac-sev"><span className="sq" aria-hidden="true" />{SEV_LABEL[a.severity]}</span>
        <span className="ma-act">{a.action}</span>
      </div>
      <div className="ma-drugs">{[...new Set(a.drugs)].map(name).join(', ')}</div>
    </div>
  );
}

/* ---- hero ------------------------------------------------------------------- */

function HeroDemo() {
  const [mode, setMode] = useState<'all' | 'medsafe'>('all');
  const all = mode === 'all';
  const tiles = all
    ? hero.all.map((a) => ({ color: SEV_COLOR[a.severity], title: a.action }))
    : [...hero.collapsed.map((a) => ({ color: SEV_COLOR[a.severity], title: a.action })),
       ...repeat(hero.all.length - hero.collapsed.length, { color: 'var(--hairline-firm)', hollow: true, title: 'Folded into a row above, or kept as a note' })];

  return (
    <section className="hd" aria-label={`Live demo: patient ${HERO_ID}`}>
      <div className="hd-head">
        <div>
          <div className="hd-title">Patient <span className="mono">{HERO_ID}</span></div>
          <div className="meta"><span className="mono">74</span> years, eGFR <span className="mono">28</span>, <span className="mono">9</span> medicines</div>
        </div>
        <Segmented label="Alert view" value={mode} onChange={setMode} segments={[
          { value: 'all', label: `Every pair (${hero.all.length})` },
          { value: 'medsafe', label: `With Medsafe (${hero.collapsed.length})` },
        ]} />
      </div>

      <div className="hd-body">
        <div className="hd-graph"><AlertGraph analysis={hero} width={380} height={236} removed={!all} /></div>
        <div className="hd-count">
          <div className={`hd-num mono${all ? '' : ' good'}`}>{all ? hero.all.length : hero.collapsed.length}</div>
          <div className="hd-num-label">{all ? 'alerts to read' : 'alerts to act on'}</div>
          <Units items={tiles} size={16} gap={4} columns={11} label={all ? `${hero.all.length} alerts` : `${hero.collapsed.length} alerts, ${hero.all.length - hero.collapsed.length} folded`} />
          <p className="hd-cap">
            {all
              ? `${about} of them are about diclofenac and ${lows} are low severity.`
              : `Stopping diclofenac clears ${hero.clearedByAnchor} of the ${hero.serious} serious interactions.`}
          </p>
        </div>
      </div>

      <div className="hd-list">
        {all ? (
          <ul className="hd-wall">
            {hero.all.map((a) => (
              <li key={a.key} className="wall-chip" style={sevVar(a)}><span className="sq" aria-hidden="true" />{a.action}</li>
            ))}
          </ul>
        ) : (
          <div className="hd-cards">{hero.collapsed.map((a) => <MiniAlert key={a.key} a={a} />)}</div>
        )}
      </div>
    </section>
  );
}

function Proof() {
  return (
    <section className="lp-proof" aria-label="Results on the simulated cohort">
      <div className="lp-wrap">
        <div className="proof-grid">
          <div className="proof">
            <div className="proof-k">Patient {HERO_ID}</div>
            <div className="proof-v mono">{hero.all.length} <span className="ink-3">to</span> {hero.collapsed.length}</div>
            <div className="proof-viz">
              <Units label={`${hero.all.length} alerts`} size={8} items={repeat(hero.all.length, { color: 'var(--ink-3)' })} />
              <span className="proof-arrow" aria-hidden="true">→</span>
              <Units label={`${hero.collapsed.length} alerts`} size={8} items={repeat(hero.collapsed.length, { color: 'var(--action)' })} />
            </div>
            <p>alerts, every pair against collapsed</p>
          </div>
          <div className="proof">
            <div className="proof-k">Across {METRICS.patients} patients</div>
            <div className="proof-v mono">{METRICS.alertsBefore.toFixed(1)} <span className="ink-3">to</span> {METRICS.alertsAfter.toFixed(1)}</div>
            <div className="proof-bars">
              <Meter value={METRICS.alertsBefore} max={METRICS.alertsBefore} width={160} height={8} color="var(--ink-3)" label={`${METRICS.alertsBefore.toFixed(1)} before`} />
              <Meter value={METRICS.alertsAfter} max={METRICS.alertsBefore} width={160} height={8} color="var(--action)" label={`${METRICS.alertsAfter.toFixed(1)} after`} />
            </div>
            <p>mean alerts per patient</p>
          </div>
          <div className="proof">
            <div className="proof-k">Near-miss recall</div>
            <div className="proof-v mono">{NEAR_MISS.caught} <span className="ink-3">/</span> {NEAR_MISS.seeded}</div>
            <div className="proof-viz">
              <Units label={`${NEAR_MISS.caught} of ${NEAR_MISS.seeded} caught`} size={8} columns={15}
                items={[...repeat(NEAR_MISS.caught, { color: 'var(--action)' }), ...repeat(NEAR_MISS.seeded - NEAR_MISS.caught, { color: 'var(--critical)', hollow: true, title: 'Missed' })]} />
            </div>
            <p>seeded serious cases still flagged after the collapse</p>
          </div>
          <div className="proof">
            <div className="proof-k">Misspelled names</div>
            <div className="proof-v mono">{resolutionPct}%</div>
            <div className="proof-viz">
              <Units label={`${res.fuzzyCorrect} of ${res.fuzzy} matched`} size={6} gap={2} columns={28}
                items={[...repeat(res.fuzzyCorrect, { color: 'var(--action)' }), ...repeat(res.fuzzy - res.fuzzyCorrect, { color: 'var(--critical)', hollow: true, title: 'Wrong match' })]} />
            </div>
            <p>matched correctly; {res.abstained} abstained instead of guessing</p>
          </div>
        </div>
        <p className="proof-note">Measured on a simulated 40-patient cohort. No real patient data. <a href="#honesty">What is real and what is not</a></p>
      </div>
    </section>
  );
}

/* ---- problem illustrations -------------------------------------------------- */

function SlipIllustration() {
  const lines: [string, boolean][] = [['Warf 5', true], ['Dynapar 50', false], ['crocine', true], ['Dolo 650', false], ['PAN-D', true], ['T. Metformin 500mg', false]];
  return (
    <div className="ill ill-slip" aria-hidden="true">
      <div className="slip">
        <div className="slip-rx">Rx</div>
        <ol>{lines.map(([t, odd]) => <li key={t}><span className={odd ? 'wavy' : undefined}>{t}</span></li>)}</ol>
      </div>
    </div>
  );
}

function StackIllustration() {
  const cards = hero.all.slice(0, 5);
  return (
    <div className="ill ill-stack" aria-hidden="true">
      <div className="stack-wrap">
        {cards.map((a, i) => (
          <div key={a.key} className="stack-card" style={{ ...sevVar(a), transform: `translate(${(cards.length - 1 - i) * 10}px, ${(cards.length - 1 - i) * 10}px)`, zIndex: i }}>
            <span className="sq" />{a.drugs.map(name).join(' + ')}
          </div>
        ))}
        <div className="stack-badge mono">×{hero.all.length}</div>
      </div>
    </div>
  );
}

function ContextIllustration() {
  return (
    <div className="ill ill-context" aria-hidden="true">
      {[28, 80].map((e) => (
        <div key={e} className="ctx-row">
          <div className="ctx-top"><span>eGFR <span className="mono">{e}</span></span><span className="ctx-flag"><Icon name="alert" size={14} />metformin renal flag</span></div>
          <EgfrGauge value={e} width={240} height={8} />
        </div>
      ))}
      <div className="ctx-same">Same flag, same alert, two very different patients</div>
    </div>
  );
}

/* ---- architecture ----------------------------------------------------------- */

const STAGES: { icon: IconName; kicker: string; title: string; desc: string; out?: string; io?: boolean; fixture?: boolean }[] = [
  { icon: 'slip', kicker: 'Input', title: 'Prescription slip', desc: 'Brands, generics, misspellings, doses.', io: true },
  { icon: 'resolve', kicker: 'Step 1', title: 'Resolve names', desc: 'Edit distance and trigrams, then rerank. Abstain when too close.', out: 'generic + confidence', fixture: true },
  { icon: 'rules', kicker: 'Step 2', title: 'Check rules', desc: 'Interactions, duplicates, renal dose, pregnancy.', out: 'findings + rule id' },
  { icon: 'context', kicker: 'Step 3', title: 'Re-score', desc: 'Renal, bleeding, sedation and age modifiers.', out: 'patient severity' },
  { icon: 'collapse', kicker: 'Step 4', title: 'Collapse and cap', desc: 'Stop the drug that clears the most. Keep five.', out: '≤ 5 actions' },
  { icon: 'screen', kicker: 'Output', title: 'Prescriber view', desc: 'Alerts, graph, slip as written, limits.', io: true },
];

function Architecture() {
  return (
    <figure className="arch" aria-label="Architecture: prescription slip to prescriber view in four steps">
      <div className="arch-grid">
        {STAGES.map((s) => (
          <div key={s.title} className={`arch-box${s.io ? ' arch-io' : ''}${s.fixture ? ' arch-fixture' : ''}`}>
            <IconTile name={s.icon} tone={s.io ? 'ink' : 'action'} />
            <div className="arch-kicker">{s.kicker}</div>
            <h3>{s.title}</h3>
            <p>{s.desc}</p>
            {s.out && <span className="arch-out">{s.out}</span>}
          </div>
        ))}
        <div className="arch-feed arch-feed-ref">
          <Icon name="database" size={18} />
          <div><h4>Reference tables</h4><p><span className="mono">{DRUGS.length}</span> generics, <span className="mono">{INTERACTIONS.length}</span> rules, <span className="mono">{EXPANDED_PAIR_COUNT}</span> pairs</p></div>
        </div>
        <div className="arch-feed arch-feed-ctx">
          <Icon name="person" size={18} />
          <div><h4>Patient context</h4><p>age, weight, eGFR, pregnancy</p></div>
        </div>
        <div className="arch-feed arch-feed-eval">
          <Icon name="chart" size={18} />
          <div><h4>Evaluation harness</h4><p>ground truth, <span className="mono">{NEAR_MISS.seeded}</span> near-misses</p></div>
        </div>
      </div>
      <figcaption className="arch-legend">
        <span><span className="lg lg-solid" aria-hidden="true" />Runs live in this prototype</span>
        <span><span className="lg lg-dashed" aria-hidden="true" />Precomputed in this prototype</span>
      </figcaption>
    </figure>
  );
}

/* ---- end to end ------------------------------------------------------------- */

function ResolveViz() {
  const pick = (raw: string) => hero.patient.meds.find((m) => m.raw === raw)!;
  return (
    <div className="rv">
      {['Warf 5', 'crocine', 'Dolo 650'].map((raw) => {
        const m = pick(raw);
        return (
          <div key={raw} className="rv-row">
            <span className="raw-chip mono">"{m.raw}"</span>
            <span className="rv-arrow" aria-hidden="true">→</span>
            <span className="res-chip">{name(m.code!)}</span>
            <Meter value={m.confidence} width={120} height={6} />
            <span className="mono">{m.confidence.toFixed(2)}</span>
          </div>
        );
      })}
      {(() => {
        const m = pick('PAN-D');
        return (
          <div className="rv-row rv-abst">
            <span className="raw-chip mono">"{m.raw}"</span>
            <span className="rv-arrow" aria-hidden="true">→</span>
            <div className="rv-cands">
              {m.candidates!.map(([c, s]) => (
                <div key={c} className="rv-cand"><span>{c}</span><Meter value={s} width={120} height={6} color="var(--warn)" /><span className="mono">{s.toFixed(2)}</span></div>
              ))}
            </div>
            <span className="tag tag-warn">too close: verify manually</span>
          </div>
        );
      })()}
    </div>
  );
}

function FindingsViz() {
  const groups = [
    { label: 'Interactions', items: hero.all.filter((a) => a.kind === 'interaction') },
    { label: 'Renal dose', items: hero.all.filter((a) => a.kind === 'renal') },
    { label: 'Duplicate', items: hero.all.filter((a) => a.kind === 'duplicate') },
  ];
  return (
    <div className="fv">
      <div className="fv-groups">
        {groups.map((g) => (
          <div key={g.label} className="fv-group">
            <Units label={`${g.label}: ${g.items.length}`} size={28} gap={6} items={g.items.map((a) => ({ color: SEV_COLOR[a.severity], title: a.action }))} />
            <div className="fv-label">{g.label} <span className="mono">{g.items.length}</span></div>
          </div>
        ))}
      </div>
      <div className="fv-legend">
        {(['high', 'medium', 'low'] as const).map((s) => (
          <span key={s}><span className="sw" style={{ background: SEV_COLOR[s] }} />{SEV_LABEL[s]} <span className="mono">{hero.all.filter((a) => a.severity === s).length}</span></span>
        ))}
        <span className="fv-total">{hero.all.length} findings</span>
      </div>
    </div>
  );
}

function RescoreViz() {
  const moved = hero.all.filter((a) => a.kind === 'interaction' && a.rescored && DEFAULT_SEV[a.tableSeverity] !== a.severity);
  return (
    <div className="sv">
      <div className="sv-lanes">
        {(['low', 'medium', 'high'] as const).map((lane) => (
          <div key={lane} className="sv-lane" style={{ ['--c' as string]: SEV_COLOR[lane] } as CSSProperties}>
            <div className="sv-lane-head"><span className="sq" />{SEV_LABEL[lane]}</div>
            {lane === 'medium' && moved.map((a) => <div key={a.key} className="sv-chip ghost">{a.drugs.map(name).join(' + ')}<span>table value</span></div>)}
            {lane === 'high' && moved.map((a) => <div key={a.key} className="sv-chip">{a.drugs.map(name).join(' + ')}<span>for this patient</span></div>)}
          </div>
        ))}
      </div>
      <div className="sv-why">
        <span>eGFR <span className="mono">28</span>: the renal modifier applies below <span className="mono">45</span></span>
        <EgfrGauge value={28} width={320} height={8} scale />
      </div>
    </div>
  );
}

function CollapseViz() {
  return (
    <div className="cv">
      <div className="cv-pair">
        <div><div className="cv-label">Before: <span className="mono">{hero.serious}</span> serious interactions</div><AlertGraph analysis={hero} width={300} height={200} /></div>
        <div><div className="cv-label">After stopping {name(anchor)}: <span className="mono">{hero.serious - hero.clearedByAnchor}</span> left</div><AlertGraph analysis={hero} width={300} height={200} removed /></div>
      </div>
    </div>
  );
}

function OutputViz() {
  return <div className="ov">{hero.collapsed.map((a) => <AlertCard key={a.key} a={a} analysis={hero} compact />)}</div>;
}

const E2E: { icon: IconName; title: string; text: string; Viz: () => JSX.Element }[] = [
  { icon: 'resolve', title: 'Read as written', text: `${hero.checked} of ${hero.patient.meds.length} lines resolve with a confidence. "PAN-D" sits between two candidates, so it goes to a manual check instead of a guess.`, Viz: ResolveViz },
  { icon: 'rules', title: 'Check the rules', text: `Every pair and every drug is checked against the tables: ${hero.all.length} findings. This is the full list a typical checker would show.`, Viz: FindingsViz },
  { icon: 'context', title: 'Re-score for her', text: 'At eGFR 28, two moderate interactions that strain the kidneys become high. The table value stays on record next to the new one.', Viz: RescoreViz },
  { icon: 'collapse', title: 'Collapse', text: `Diclofenac sits on ${hero.clearedByAnchor} of the ${hero.serious} serious interactions and the rule table allows stopping it. Warfarin is never offered.`, Viz: CollapseViz },
  { icon: 'screen', title: 'Show the prescriber', text: `${hero.collapsed.length} alerts instead of ${hero.all.length}, each with an action and the rule behind it. A footer keeps the decision with the clinician.`, Viz: OutputViz },
];

function EndToEnd() {
  const [i, setI] = useState(0);
  const step = E2E[i];
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight') setI((v) => Math.min(E2E.length - 1, v + 1));
    if (e.key === 'ArrowLeft') setI((v) => Math.max(0, v - 1));
  };
  return (
    <div className="e2e">
      <div className="e2e-tabs" role="tablist" aria-label="End-to-end steps" onKeyDown={onKey}>
        {E2E.map((s, n) => (
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
            {i < E2E.length - 1 && <button type="button" className="btn btn-primary btn-sm" onClick={() => setI(i + 1)}>Next step</button>}
          </div>
        </div>
        <div className="e2e-viz"><step.Viz /></div>
      </div>
    </div>
  );
}

/* ---- difference ------------------------------------------------------------- */

function Compare() {
  return (
    <div className="cmp">
      <figure className="cmp-col">
        <figcaption><Icon name="alert" size={16} />Typical interaction checker</figcaption>
        <div className="mock mock-them" aria-hidden="true">
          <div className="mock-bar">Drug interaction warnings <span className="mono">{hero.all.length}</span></div>
          <ul>
            {hero.all.map((a) => (
              <li key={a.key}><Icon name="alert" size={12} /><span>{findingLabel(a)}</span><span className="mock-btn">Override</span></li>
            ))}
          </ul>
          <div className="mock-foot"><span className="mock-btn">Override all</span></div>
        </div>
        <p>Every pair, the same severity for every patient. Five warnings about one drug, and most get overridden.</p>
      </figure>
      <figure className="cmp-col cmp-us">
        <figcaption><Icon name="check" size={16} />Medsafe</figcaption>
        <div className="mock mock-us" aria-hidden="true">
          <div className="mock-bar">Patient {HERO_ID} <span className="mono">{hero.collapsed.length}</span></div>
          <div className="mock-cards">{hero.collapsed.map((a) => <MiniAlert key={a.key} a={a} />)}</div>
          <div className="mock-folded">
            <div><Units label="Folded" size={8} gap={2} items={repeat(folded.length, { color: 'var(--critical)', hollow: true })} />{folded.length} folded into the {name(anchor)} row</div>
            <div><Units label="Notes" size={8} gap={2} items={repeat(lows, { color: 'var(--ink-3)', hollow: true })} />{lows} low-severity notes, one click away</div>
          </div>
          <div className="mock-foot">Checked {hero.checked} of {hero.patient.meds.length} medicines. A clinician decides.</div>
        </div>
        <p>One decision per cluster, re-scored for this patient, with the rule behind every action.</p>
      </figure>
    </div>
  );
}

const CONTRAST: { icon: IconName; aspect: string; them: string; us: string }[] = [
  { icon: 'slip', aspect: 'Input', them: 'Clean generic names only', us: 'The slip as written' },
  { icon: 'question', aspect: 'Unclear names', them: 'Guessed silently', us: 'Abstains and asks for a check' },
  { icon: 'context', aspect: 'Severity', them: 'Fixed for every patient', us: 'Re-scored for this patient' },
  { icon: 'collapse', aspect: 'Output', them: 'One alert per pair', us: 'One change per cluster' },
  { icon: 'shield', aspect: 'Nothing found', them: '"No interactions"', us: '"No issue found in what was seen"' },
  { icon: 'chart', aspect: 'Evaluation', them: 'Alert counts, if anything', us: 'Volume and recall, misses listed' },
];

/* ---- page ------------------------------------------------------------------- */

const STACK: [string, string, string, string][] = [
  ['R', 'React', '18.3', 'Screens, state and the walkthrough'],
  ['TS', 'TypeScript', '5.6 strict', 'Typed rule engine and data tables'],
  ['V', 'Vite', '5.4', 'Dev server and production build'],
  ['RR', 'React Router', '6.28', 'Client routing and deep links'],
  ['SVG', 'Hand-written SVG', 'no library', 'Graph, charts and diagrams'],
  ['CSS', 'CSS tokens', 'one file', 'IBM Plex, square corners, status colour'],
];

const SHIP: [IconName, string, string][] = [
  ['commit', 'Push to main', 'GitHub'],
  ['box', 'Strict build', 'npm ci, tsc, Vite'],
  ['globe', 'Static hosting', 'Pages or Vercel'],
  ['browser', 'Runs on device', 'App, rules and data'],
];

const WALK: [IconName, string, string][] = [
  ['queue', 'The queue', 'Forty prescriptions ranked by urgency'],
  ['person', `Patient ${HERO_ID}`, 'Context first: eGFR 28, nine medicines'],
  ['toggle', 'The collapse', 'Eleven alerts to three, in one click'],
  ['graph', 'The alert graph', 'Why stopping one drug is enough'],
  ['slip', 'The slip as written', 'Matches, confidence, one abstention'],
  ['chart', 'Method and evaluation', 'Re-scoring, recall, and the misses'],
];

export function Landing() {
  const { user } = useAuth();
  const demoHref = user ? '/app' : '/login';
  return (
    <div className="lp">
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-inner">
          <Link to="/" className="lp-brand"><span className="brand-mark" aria-hidden="true" />Medsafe</Link>
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
                Medsafe reads a prescription the way it was written, re-scores every flag for the patient in front of you, and
                turns each cluster of alerts into the one change that clears it.
              </p>
              <div className="lp-ctas">
                <Link to={demoHref} className="btn btn-primary">Open the live demo</Link>
                <Link to="/login?tour=1" className="btn btn-secondary">Take the guided walkthrough</Link>
              </div>
              <ul className="hero-points">
                <li><Icon name="slip" size={16} />Reads brands, generics and misspellings</li>
                <li><Icon name="context" size={16} />Re-scores for kidney function, age and weight</li>
                <li><Icon name="collapse" size={16} />One action per cluster, at most five</li>
              </ul>
            </div>
            <HeroDemo />
          </div>
        </section>

        <Proof />

        <section id="problem" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">The warning that matters gets lost among the ones that do not.</h2>
            <p className="lp-lead lp-measure">
              Clinicians override 49% to 96% of drug safety alerts in computerised order entry.<sup><a href="#ref-1" id="cite-1">1</a></sup> Three
              things cause it, and Medsafe answers each one.
            </p>
            <div className="lp-three">
              <article className="ill-card"><SlipIllustration /><h3 className="lp-h3">Slips are messy</h3><p>Brands, generics, misspellings and doses on one list. Tools that expect clean names miss lines or match them wrongly.</p></article>
              <article className="ill-card"><StackIllustration /><h3 className="lp-h3">One alert per pair</h3><p>Nine medicines raise eleven warnings. Five are about the same drug and three are low severity.</p></article>
              <article className="ill-card"><ContextIllustration /><h3 className="lp-h3">Context is ignored</h3><p>The metformin renal flag fires the same way at eGFR 28 and 80. At 28 it should stop the drug; at 80 it is a yearly check.</p></article>
            </div>
          </div>
        </section>

        <section id="architecture" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <h2 className="lp-h2">Four steps between the slip and the screen.</h2>
            <p className="lp-lead lp-measure">
              Every step records why it decided what it did. No model writes an action: each suggestion traces back to a rule id
              such as <span className="mono">NSAID-ACEI-01</span>.
            </p>
            <Architecture />
          </div>
        </section>

        <section id="end-to-end" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">One prescription, end to end.</h2>
            <p className="lp-lead lp-measure">Patient {HERO_ID}: 74 years old, eGFR 28, nine medicines. Step through what the app computes for her.</p>
            <EndToEnd />
          </div>
        </section>

        <section id="difference" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <h2 className="lp-h2">The same prescription, two screens.</h2>
            <Compare />
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
              <article className="trust"><IconTile name="shield" tone="ok" /><h3 className="lp-h3">Never calls a patient safe</h3><p>It says no issue was found in what was seen, counts what it could not check, and leaves the decision with the clinician.</p></article>
              <article className="trust"><IconTile name="question" tone="warn" /><h3 className="lp-h3">Abstains instead of guessing</h3><p>A name too close to two candidates is marked unresolved and kept out of the checks, so a wrong match cannot hide a real interaction.</p></article>
              <article className="trust"><IconTile name="flag" tone="critical" /><h3 className="lp-h3">Reports its misses</h3><p>Real: rules, re-scoring, collapse and cap. Simulated: patients, name-matching results and near-miss labels. Both misses are listed.</p></article>
            </div>
          </div>
        </section>

        <section id="stack" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">A small stack, on purpose.</h2>
            <p className="lp-lead lp-measure">No backend, no database, no model in the request path. The same prescription gives the same screen every time.</p>
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
              <li>A name-matching service in place of the precomputed results, with the same abstention rule.</li>
              <li>Licensed drug reference data in place of the reduced tables.</li>
              <li>Hospital record integration through HL7 FHIR medication requests.</li>
              <li>Prospective evaluation against near-misses labelled by pharmacists.</li>
            </ul>
          </div>
        </section>

        <section id="walkthrough" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <div className="walk-head">
              <div>
                <h2 className="lp-h2">See it in two minutes.</h2>
                <p className="lp-lead">Sign in with a demo account and a guided walkthrough starts on its own, moving through the app and highlighting one thing at a time.</p>
              </div>
              <div className="lp-ctas">
                <Link to="/login?tour=1" className="btn btn-primary">Start the walkthrough</Link>
                <Link to={demoHref} className="btn btn-secondary">Explore on my own</Link>
              </div>
            </div>
            <ol className="walk-strip">
              {WALK.map(([icon, t, s], n) => (
                <li key={t}>
                  <div className="walk-top"><span className="mono">{n + 1}</span><IconTile name={icon} size={32} /></div>
                  <strong>{t}</strong>
                  <span>{s}</span>
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
            <span className="meta">Prototype on a simulated dataset. No real patient data was used. A clinician decides.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
