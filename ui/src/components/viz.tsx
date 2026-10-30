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
  slip: 'M6 3h9l3 3v15H6z M15 3v3h3 M9 10h6 M9 14h6 M9 18h4',
  resolve: 'M10.5 4a6.5 6.5 0 1 1 0 13a6.5 6.5 0 0 1 0-13z M15.5 15.5L21 21 M8 10.5h5',
  rules: 'M4 6h2 M9 6h11 M4 12h2 M9 12h11 M4 18h2 M9 18h11',
  context: 'M4 17a8 8 0 0 1 16 0 M12 17l4-5 M4 20h16',
  collapse: 'M3 4h4v4H3z M17 4h4v4h-4z M10 16h4v4h-4z M7 6h10 M6 8l5 8 M18 8l-5 8',
  screen: 'M3 4h18v12H3z M8 20h8 M12 16v4 M6 8h8 M6 12h5',
  database: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3v12c0 1.7-3.6 3-8 3s-8-1.3-8-3z M4 6c0 1.7 3.6 3 8 3s8-1.3 8-3 M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  chart: 'M4 20V11 M10 20V5 M16 20v-6 M3 20h18',
  question: 'M12 3a9 9 0 1 1 0 18a9 9 0 0 1 0-18z M9.5 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-.9.8-.9 1.5V14 M12 17v.5',
  commit: 'M3 12h6 M15 12h6 M12 9a3 3 0 1 1 0 6a3 3 0 0 1 0-6z',
  box: 'M4 7l8-4l8 4v10l-8 4l-8-4z M4 7l8 4l8-4 M12 11v10',
  globe: 'M12 3a9 9 0 1 1 0 18a9 9 0 0 1 0-18z M3 12h18 M12 3c3 3 3 15 0 18 M12 3c-3 3-3 15 0 18',
  browser: 'M3 4h18v16H3z M3 8h18 M6 6h1 M9 6h1',
  check: 'M4 12l5 5L20 6',
  queue: 'M4 5h16 M4 10h16 M4 15h10 M4 20h7',
  toggle: 'M3 7h18v10H3z M12 7v10 M15 12h3',
  graph: 'M5 5h3v3H5z M16 5h3v3h-3z M10.5 16h3v3h-3z M8 6.5h8 M7 8l4 8 M17 8l-4 8',
  lock: 'M6 11h12v10H6z M8.5 11V8a3.5 3.5 0 0 1 7 0v3',
  x: 'M6 6l12 12 M18 6L6 18',
  clock: 'M12 3a9 9 0 1 1 0 18a9 9 0 0 1 0-18z M12 7v5l3 3',
  pill: 'M9.5 4.5a4.95 4.95 0 0 1 7 7l-5 5a4.95 4.95 0 0 1-7-7z M7 9.5l7 7',
  flask: 'M9 3h6 M10 3v6l-5 10h14l-5-10V3 M7.5 14h9',
  stethoscope: 'M6 3v5a4 4 0 0 0 8 0V3 M10 12v3a4 4 0 0 0 8 0v-3 M18 8a2 2 0 1 1 0 4a2 2 0 0 1 0-4z',
  eye: 'M2 12c2.5-4.5 6-7 10-7s7.5 2.5 10 7c-2.5 4.5-6 7-10 7s-7.5-2.5-10-7z M12 9a3 3 0 1 1 0 6a3 3 0 0 1 0-6z',
  bell: 'M6 16v-5a6 6 0 0 1 12 0v5l2 2H4z M10 21h4',
  swap: 'M4 8h14 M15 5l3 3l-3 3 M20 16H6 M9 13l-3 3l3 3',
  phone: 'M7 2h10v20H7z M11 18h2',
  guide: 'M5 4h11l3 3v13H5z M8 9h8 M8 13h8 M8 17h5',
  bolt: 'M13 3L5 13h6l-1 8l8-10h-6z',
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

export function IconTile({ name, tone = 'action', size = 40 }: { name: IconName; tone?: 'action' | 'ink' | 'warn' | 'critical' | 'ok'; size?: number }) {
  return <span className={`icon-tile tone-${tone}`} style={{ width: size, height: size }}><Icon name={name} size={Math.round(size * 0.5)} /></span>;
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
