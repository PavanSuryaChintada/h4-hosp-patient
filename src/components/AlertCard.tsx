import { name, type Alert, type Analysis } from '../data/engine';
import { Meter, SEV_COLOR, Units, repeat } from './viz';

const SEV_LABEL = { high: 'High', medium: 'Medium', low: 'Low' };
const DEFAULT_SEV: Record<string, string> = { major: 'high', moderate: 'medium', minor: 'low' };

export function rescoreNote(a: Alert): string | null {
  if (a.kind === 'renal') return `renal flag, ${a.rescored}`;
  if (a.rescored && DEFAULT_SEV[a.tableSeverity] !== a.severity) return `table ${a.tableSeverity}, re-scored for ${a.rescored}`;
  if (a.kind === 'interaction') return `table ${a.tableSeverity}`;
  return null;
}

function DrugChips({ a }: { a: Alert }) {
  if (a.kind === 'cluster') {
    return (
      <div className="chips-row">
        <span className="drug-chip anchor">{name(a.drugs[0])}</span>
        <span className="chips-sep">with</span>
        {a.drugs.slice(1).map((d) => <span key={d} className="drug-chip">{name(d)}</span>)}
      </div>
    );
  }
  if (a.kind === 'duplicate' && a.drugs[0] === a.drugs[1]) {
    return <div className="chips-row"><span className="drug-chip">{name(a.drugs[0])}</span><span className="chips-sep">listed twice</span></div>;
  }
  return (
    <div className="chips-row">
      {a.drugs.map((d, i) => (
        <span key={d + i} className="chips-pair">
          {i > 0 && <span className="chips-sep">+</span>}
          <span className="drug-chip">{name(d)}</span>
        </span>
      ))}
    </div>
  );
}

/** One alert, as a card. `compact` drops the mechanism and rule lines for the every-pair view. */
export function AlertCard({ a, analysis, compact = false }: { a: Alert; analysis?: Analysis; compact?: boolean }) {
  const re = rescoreNote(a);
  const cleared = a.kind === 'cluster' && analysis ? analysis.clearedByAnchor : 0;
  return (
    <article className={`alert-card s-${a.severity}${compact ? ' compact' : ''}`} style={{ ['--c' as string]: SEV_COLOR[a.severity] }}>
      <header className="ac-head">
        <span className="ac-sev"><span className="sq" aria-hidden="true" />{SEV_LABEL[a.severity]}</span>
        <span className="ac-type">{a.type}</span>
        {re && <span className="ac-re">{re}</span>}
        <span className="ac-conf" title="Confidence">
          <Meter value={a.confidence} width={48} color={a.severity === 'low' ? 'var(--ink-3)' : 'var(--action)'} />
          <span className="mono">{a.confidence.toFixed(2)}</span>
        </span>
      </header>
      <p className="ac-action">{a.action}</p>
      <DrugChips a={a} />
      {a.kind === 'cluster' && analysis && (
        <div className="ac-clears">
          <Units label={`Clears ${cleared} of ${analysis.serious} serious interactions`} size={10} gap={3}
            items={[...repeat(cleared, { color: 'var(--critical)' }), ...repeat(analysis.serious - cleared, { color: 'var(--critical)', hollow: true })]} />
          <span>clears <span className="mono">{cleared}</span> of <span className="mono">{analysis.serious}</span> serious interactions</span>
        </div>
      )}
      {!compact && a.note && <p className="ac-note">{a.note}</p>}
      {!compact && <p className="ac-src">{a.source}</p>}
    </article>
  );
}
