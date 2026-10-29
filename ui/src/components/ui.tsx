import type { ReactNode } from 'react';
import type { Severity } from '../data/engine';

export type Level = Severity | 'cleared';

const LABEL: Record<Level, string> = { high: 'High', medium: 'Medium', low: 'Low', cleared: 'Cleared' };

/** Status is always bar + square + text, so it still reads without colour. Renders a table cell. */
export function StatusCell({ level }: { level: Level }) {
  return (
    <td className={`sev s-${level}`}>
      <span className="sq" aria-hidden="true" />
      <span className="lbl">{LABEL[level]}</span>
    </td>
  );
}

export function StatusInline({ level }: { level: Level }) {
  return (
    <span className={`s-${level}`} style={{ whiteSpace: 'nowrap' }}>
      <span className="sq" aria-hidden="true" style={{ display: 'inline-block', width: 6, height: 6, background: 'var(--c)', marginRight: 8, verticalAlign: 1 }} />
      <span style={{ color: 'var(--c)', fontWeight: 500 }}>{LABEL[level]}</span>
    </span>
  );
}

export type Segment<T extends string> = { value: T; label: string; count?: number };

export function Segmented<T extends string>({ value, onChange, segments, label }: {
  value: T; onChange: (v: T) => void; segments: Segment<T>[]; label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
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
