// Small visual primitives shared by the landing page and the console.
// Counts are drawn as unit squares (the same square used by every status mark).

import type { ReactNode } from 'react';
import type { Severity } from '../data/engine';

export const SEV_COLOR: Record<Severity | 'cleared', string> = {
  high: 'var(--critical)', medium: 'var(--warn)', low: 'var(--ink-3)', cleared: 'var(--ok)',
};

export type Unit = { color: string; hollow?: boolean; title?: string };

/** A row (or grid) of squares, one per item. */
export function Units({ items, size = 8, gap = 3, columns, label }: { items: Unit[]; size?: number; gap?: number; columns?: number; label: string }) {
  return (
    <span className="units" role="img" aria-label={label}
      style={{ gridTemplateColumns: `repeat(${columns ?? items.length}, ${size}px)`, gap, gridAutoRows: size }}>
      {items.map((u, i) => (
        <span key={i} title={u.title} style={u.hollow ? { border: `1px solid ${u.color}` } : { background: u.color }} />
      ))}
    </span>
  );
}

export const repeat = (n: number, u: Unit): Unit[] => Array.from({ length: n }, () => u);

/** Thin horizontal meter. */
export function Meter({ value, max = 1, width = 64, height = 4, color = 'var(--action)', label }: { value: number; max?: number; width?: number; height?: number; color?: string; label?: string }) {
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <span className="meter" style={{ width, height }} role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <span style={{ width: `${pct * 100}%`, background: color }} />
    </span>
  );
}

/** eGFR on a 0–120 scale with the 30 / 45 / 60 thresholds the renal rules use. */
export function EgfrGauge({ value, width = 96, height = 6, scale = false }: { value: number; width?: number; height?: number; scale?: boolean }) {
  const max = 120;
  const x = (v: number) => `${(Math.min(v, max) / max) * 100}%`;
  const color = value < 30 ? 'var(--critical)' : value < 45 ? 'var(--warn)' : 'var(--ok)';
  return (
    <span className="egfr" style={{ width }} role="img" aria-label={`eGFR ${value}${value < 45 ? ', low' : ''}`}>
      <span className="egfr-track" style={{ height }}>
        <span className="egfr-zone" style={{ left: 0, width: x(30), background: 'var(--critical)' }} />
        <span className="egfr-zone" style={{ left: x(30), width: `calc(${x(45)} - ${x(30)})`, background: 'var(--warn)' }} />
        <span className="egfr-zone" style={{ left: x(45), right: 0, background: 'var(--ok)' }} />
        <span className="egfr-mark" style={{ left: x(value), background: color, height: height + 6, top: -3 }} />
      </span>
      {scale && (
        <span className="egfr-scale">
          {[0, 30, 45, 60, 90, 120].map((t) => <span key={t} style={{ left: x(t) }}>{t}</span>)}
        </span>
      )}
    </span>
  );
}

/** One bar split into labelled segments. */
export function StackedBar({ segments, height = 12, label }: { segments: { value: number; color: string; name: string }[]; height?: number; label: string }) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div className="stacked" role="img" aria-label={label}>
      <div className="stacked-bar" style={{ height }}>
        {segments.map((s) => s.value > 0 && <span key={s.name} style={{ width: `${(s.value / total) * 100}%`, background: s.color }} title={`${s.name}: ${s.value}`} />)}
      </div>
      <div className="stacked-legend">
        {segments.map((s) => (
          <span key={s.name}><span className="sw" style={{ background: s.color }} />{s.name} <span className="mono">{s.value}</span></span>
        ))}
      </div>
    </div>
  );
}

const PATHS: Record<string, string> = {
  slip: 'M6 3h9l3 3v15H6z M15 3v3h3 M9 10h6 M9 14h6 M9 18h4',
  resolve: 'M10.5 4a6.5 6.5 0 1 1 0 13a6.5 6.5 0 0 1 0-13z M15.5 15.5L21 21 M8 10.5h5',
  rules: 'M4 6h2 M9 6h11 M4 12h2 M9 12h11 M4 18h2 M9 18h11',
  context: 'M4 17a8 8 0 0 1 16 0 M12 17l4-5 M4 20h16',
  collapse: 'M3 4h4v4H3z M17 4h4v4h-4z M10 16h4v4h-4z M7 6h10 M6 8l5 8 M18 8l-5 8',
  screen: 'M3 4h18v12H3z M8 20h8 M12 16v4 M6 8h8 M6 12h5',
  database: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3v12c0 1.7-3.6 3-8 3s-8-1.3-8-3z M4 6c0 1.7 3.6 3 8 3s8-1.3 8-3 M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  person: 'M12 4a3.5 3.5 0 1 1 0 7a3.5 3.5 0 0 1 0-7z M5 20c0-4 3-6.5 7-6.5s7 2.5 7 6.5',
  chart: 'M4 20V11 M10 20V5 M16 20v-6 M3 20h18',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9c-4.5-1-8-4-8-9V6z M8.5 12l2.5 2.5l4.5-5',
  question: 'M12 3a9 9 0 1 1 0 18a9 9 0 0 1 0-18z M9.5 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-.9.8-.9 1.5V14 M12 17v.5',
  flag: 'M5 21V4 M5 4h12l-2.5 4l2.5 4H5',
  commit: 'M3 12h6 M15 12h6 M12 9a3 3 0 1 1 0 6a3 3 0 0 1 0-6z',
  box: 'M4 7l8-4l8 4v10l-8 4l-8-4z M4 7l8 4l8-4 M12 11v10',
  globe: 'M12 3a9 9 0 1 1 0 18a9 9 0 0 1 0-18z M3 12h18 M12 3c3 3 3 15 0 18 M12 3c-3 3-3 15 0 18',
  browser: 'M3 4h18v16H3z M3 8h18 M6 6h1 M9 6h1',
  alert: 'M12 3l10 18H2z M12 10v5 M12 17.5v.5',
  check: 'M4 12l5 5L20 6',
  queue: 'M4 5h16 M4 10h16 M4 15h10 M4 20h7',
  toggle: 'M3 7h18v10H3z M12 7v10 M15 12h3',
  graph: 'M5 5h3v3H5z M16 5h3v3h-3z M10.5 16h3v3h-3z M8 6.5h8 M7 8l4 8 M17 8l-4 8',
  lock: 'M6 11h12v10H6z M8.5 11V8a3.5 3.5 0 0 1 7 0v3',
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
