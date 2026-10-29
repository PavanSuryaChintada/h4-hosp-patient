import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { store, TOUR_PENDING_KEY, TOUR_SEEN_KEY } from '../auth';
import { METRICS } from '../data/engine';
import { NEAR_MISS } from '../data/evaluation';
import { HERO_ID } from '../data/patients';

type Step = { path: string; target?: string; title: string; body: string };

const HERO = `/app/patient/${HERO_ID}`;

export const STEPS: Step[] = [
  { path: '/app', title: 'Welcome to Medsafe', body: 'A second pair of eyes for prescriptions. This walkthrough takes about two minutes. Use the buttons or the arrow keys; Esc closes it.' },
  { path: '/app', target: 'queue-filter', title: 'The prescribing queue', body: 'Forty prescriptions waiting for review, highest severity first. Filter by severity; each segment shows its count.' },
  { path: '/app', target: 'hero-row', title: `Start with patient ${HERO_ID}`, body: 'Nine medicines and eleven raw warnings, shown here as three. Next opens the patient.' },
  { path: HERO, target: 'strip', title: 'Patient context comes first', body: 'Age, weight, kidney function and pregnancy decide how serious each flag is. eGFR 28 is marked low.' },
  { path: HERO, target: 'alerts', title: 'Three alerts, not eleven', body: 'The top row is one decision: stop diclofenac, which clears 4 of the 5 serious interactions. Every action and rule id comes from the rule tables.' },
  { path: `${HERO}?view=all`, target: 'alert-toggle', title: 'What a typical checker shows', body: 'Every pair: 11 alerts, 5 of them about the same drug, 3 low severity. This is alert fatigue. The toggle switches between the two views at any time.' },
  { path: HERO, target: 'graph', title: 'Why one change is enough', body: 'Drugs are nodes and serious interactions are red edges. Diclofenac sits on four of the five, so stopping it clears them.' },
  { path: HERO, target: 'meds', title: 'Read the slip as written', body: 'Each line shows the text on the slip, what it resolved to, and the confidence. "PAN-D" is too close to call, so Medsafe asks for a manual check instead of guessing.' },
  { path: HERO, target: 'limits', title: 'It never says safe', body: 'Every patient carries this footer: what was checked, what was not, and that a clinician decides.' },
  { path: '/app/resolution', target: 'resolution-stat', title: 'Name matching, audited', body: 'Every raw string in the cohort with its match, confidence and a ground-truth check. Wrong matches are listed, not hidden.' },
  { path: '/app/method', target: 'method-pair', title: 'Same flag, different patient', body: 'Metformin is high at eGFR 28 and low at eGFR 80. Severity is re-scored for each patient, and both values are kept.' },
  {
    path: '/app/evaluation', target: 'eval-stats', title: 'Two numbers that move together',
    body: `Alerts per patient fall from ${METRICS.alertsBefore.toFixed(1)} to ${METRICS.alertsAfter.toFixed(1)} while near-miss recall holds at ${NEAR_MISS.caught} of ${NEAR_MISS.seeded}. The two misses are listed below the chart.`,
  },
  { path: HERO, title: 'Your turn', body: `You are on patient ${HERO_ID}. Try the collapse toggle yourself. Restart this walkthrough from the top bar at any time.` },
];

type TourApi = { start: () => void; active: boolean };
const TourContext = createContext<TourApi>({ start: () => {}, active: false });
export const useTour = () => useContext(TourContext);

export function TourProvider({ children }: { children: ReactNode }) {
  const [index, setIndex] = useState<number | null>(null);

  const start = useCallback(() => {
    store.set(TOUR_SEEN_KEY, '1');
    setIndex(0);
  }, []);

  useEffect(() => {
    if (store.get(TOUR_PENDING_KEY) === '1') {
      store.remove(TOUR_PENDING_KEY);
      start();
    }
  }, [start]);

  return (
    <TourContext.Provider value={{ start, active: index !== null }}>
      {children}
      {index !== null && (
        <TourOverlay
          index={index}
          onBack={() => setIndex((i) => Math.max(0, (i ?? 0) - 1))}
          onNext={() => setIndex((i) => ((i ?? 0) + 1 < STEPS.length ? (i ?? 0) + 1 : null))}
          onClose={() => setIndex(null)}
        />
      )}
    </TourContext.Provider>
  );
}

const TOPBAR = 48;
const PAD = 4;

function TourOverlay({ index, onBack, onNext, onClose }: { index: number; onBack: () => void; onNext: () => void; onClose: () => void }) {
  const step = STEPS[index];
  const navigate = useNavigate();
  const location = useLocation();
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [ready, setReady] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const last = index === STEPS.length - 1;

  // Move to the step's page. Only on step change, so the reader can wander off without being pulled back.
  useEffect(() => {
    if (location.pathname + location.search !== step.path) navigate(step.path);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  // Find the target once the page has rendered, bring it into view, then follow it on scroll and resize.
  useEffect(() => {
    setRect(null);
    setReady(!step.target);
    if (!step.target) return;
    let el: Element | null = null;
    let raf = 0;
    let tries = 0;
    const update = () => { if (el) setRect(el.getBoundingClientRect()); };
    const seek = () => {
      el = document.querySelector(`[data-tour="${step.target}"]`);
      if (el) {
        const r = el.getBoundingClientRect();
        window.scrollTo({ top: Math.max(0, r.top + window.scrollY - TOPBAR - 24) });
        update();
        setReady(true);
      } else if (tries++ < 90) {
        raf = requestAnimationFrame(seek);
      } else {
        setReady(true); // target not on screen (e.g. filtered out): fall back to a centred card
      }
    };
    raf = requestAnimationFrame(seek);
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, [index, step.target]);

  // Place the card below the target, else above it, else in the bottom-right corner.
  useLayoutEffect(() => {
    const pop = popRef.current;
    if (!pop || !ready) return;
    const vw = window.innerWidth, vh = window.innerHeight;
    const w = pop.offsetWidth, h = pop.offsetHeight;
    if (!rect) {
      setPos({ top: Math.max(16, (vh - h) / 2), left: Math.max(16, (vw - w) / 2) });
      return;
    }
    const gap = 12;
    let top = rect.bottom + PAD + gap;
    let left = Math.min(Math.max(rect.left, 16), vw - w - 16);
    if (top + h > vh - 16) top = rect.top - PAD - gap - h;
    if (top < TOPBAR + 8) { top = vh - h - 24; left = vw - w - 24; }
    setPos({ top, left });
  }, [rect, index, ready]);

  useEffect(() => { nextRef.current?.focus({ preventScroll: true }); }, [index]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowRight') onNext();
      else if (e.key === 'ArrowLeft') onBack();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onBack, onNext, onClose]);

  return (
    <div className="tour" aria-live="polite">
      {rect ? (
        <div className="tour-spot" style={{ top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }} />
      ) : (
        <div className="tour-scrim" onClick={onClose} />
      )}
      <div ref={popRef} className="tour-pop" role="dialog" aria-labelledby="tour-title"
        style={ready && pos ? { top: pos.top, left: pos.left } : { visibility: 'hidden', top: 0, left: 0 }}>
        <div className="tour-progress" aria-hidden="true">
          {STEPS.map((_, i) => <span key={i} className={i <= index ? 'on' : undefined} />)}
        </div>
        <div className="tour-count">Step <span className="mono">{index + 1}</span> of <span className="mono">{STEPS.length}</span></div>
        <h2 id="tour-title" className="section">{step.title}</h2>
        <p className="tour-body">{step.body}</p>
        <div className="tour-actions">
          <button type="button" className="btn-link" onClick={onClose}>{last ? 'Close' : 'Skip walkthrough'}</button>
          <div className="tour-nav">
            {index > 0 && <button type="button" className="btn btn-secondary btn-sm" onClick={onBack}>Back</button>}
            <button ref={nextRef} type="button" className="btn btn-primary btn-sm" onClick={onNext}>{last ? 'Finish' : 'Next'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
