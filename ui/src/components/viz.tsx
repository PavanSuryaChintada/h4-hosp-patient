// Small visual primitives. Counts are drawn as unit squares, the same square every status mark uses.

import type { ReactNode } from 'react';

export type Unit = { color: string; hollow?: boolean; title?: string };

/** A row (or grid) of squares, one per item. */
export function Units({ items, size = 8, gap = 3, columns, label }: { items: Unit[]; size?: number; gap?: number; columns?: number; label: string }) {
  return (
    <span className="units" role="img" aria-label={label}
      style={{ gridTemplateColumns: `repeat(${columns ?? Math.max(items.length, 1)}, ${size}px)`, gap, gridAutoRows: size }}>
      {items.map((u, i) => (
        <span key={i} title={u.title} style={u.hollow ? { border: `1px solid ${u.color}` } : { background: u.color }} />
      ))}
    </span>
  );
}

export const repeat = (n: number, u: Unit): Unit[] => Array.from({ length: Math.max(0, n) }, () => u);

/** Thin horizontal meter. */
export function Meter({ value, max = 1, width = 64, height = 4, color = 'var(--action)', label }: { value: number; max?: number; width?: number; height?: number; color?: string; label?: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  return (
    <span className="meter" style={{ width, height }} role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <span style={{ width: `${pct * 100}%`, background: color }} />
    </span>
  );
}

const PATHS: Record<string, string> = {
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9c-4.5-1-8-4-8-9V6z M8.5 12l2.5 2.5l4.5-5',
  flag: 'M5 21V4 M5 4h12l-2.5 4l2.5 4H5',
  alert: 'M12 3l10 18H2z M12 10v5 M12 17.5v.5',
  person: 'M12 4a3.5 3.5 0 1 1 0 7a3.5 3.5 0 0 1 0-7z M5 20c0-4 3-6.5 7-6.5s7 2.5 7 6.5',
  arrow: 'M4 12h15 M14 7l5 5l-5 5',
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 20, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="square" strokeLinejoin="miter" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

export function Kpi({ label, value, children, sub }: { label: string; value: ReactNode; children?: ReactNode; sub?: ReactNode }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {children && <div className="kpi-viz">{children}</div>}
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
