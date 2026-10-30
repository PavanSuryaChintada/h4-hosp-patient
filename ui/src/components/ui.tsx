import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { Severity } from '../data/contract';
import { SEVERITY_LABEL, SEVERITY_TONE } from '../data/format';
import { useData } from '../data/load';

/** Status is always bar + square + text, so it still reads without colour. Renders a table cell. */
export function StatusCell({ severity }: { severity: Severity }) {
  return (
    <td className="sev" style={{ ['--c' as string]: SEVERITY_TONE[severity] }}>
      <span className="sq" aria-hidden="true" />
      <span className="lbl">{SEVERITY_LABEL[severity]}</span>
    </td>
  );
}

export function StatusInline({ severity }: { severity: Severity }) {
  return (
    <span className="status" style={{ ['--c' as string]: SEVERITY_TONE[severity] }}>
      <span className="sq" aria-hidden="true" />{SEVERITY_LABEL[severity]}
    </span>
  );
}

export type Segment<T extends string> = { value: T; label: string; count?: number };

export function Segmented<T extends string>({ value, onChange, segments, label, className }: {
  value: T; onChange: (v: T) => void; segments: Segment<T>[]; label: string; className?: string;
}) {
  return (
    <div className={`seg${className ? ` ${className}` : ''}`} role="group" aria-label={label}>
      {segments.map((s) => (
        <button key={s.value} type="button" aria-pressed={s.value === value} onClick={() => onChange(s.value)}>
          {s.label}
          {s.count !== undefined && <span className="count">{s.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Stat({ caption, figure, sub, color }: { caption: string; figure: ReactNode; sub: ReactNode; color?: string }) {
  return (
    <div className="stat">
      <div className="cap">{caption}</div>
      <div className="fig" style={{ color }}>{figure}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

/**
 * The state for a panel whose pipeline stage has not landed. Grey, never red: it is the absence
 * of output, not a finding, and it must never read as "nothing found".
 */
export function NotBuilt({ stage, what }: { stage: string; what: ReactNode }) {
  const { x } = useData();
  const phase = x.stages.find((s) => s.id === stage)?.phase;
  return (
    <div className="not-built" role="note">
      <span className="nb-head">Not built yet{phase ? `: ${phase}` : ''}</span>
      <span>{what} This panel fills from pipeline output when it lands. Nothing here is computed in the browser.</span>
    </div>
  );
}

/** A short inline "not built" marker for a single figure. */
export function NotBuiltValue({ stage }: { stage: string }) {
  const { x } = useData();
  const phase = x.stages.find((s) => s.id === stage)?.phase;
  return <span className="nb-inline" title={`Needs the ${stage} stage${phase ? `, ${phase}` : ''}`}>not built</span>;
}

export function PatientLink({ id }: { id: string }) {
  return <Link className="mono" to={`/app/patient/${id}`}>{id}</Link>;
}
