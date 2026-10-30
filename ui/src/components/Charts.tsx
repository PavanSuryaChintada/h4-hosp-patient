// Hand-written SVG charts (no chart library, SHARED-DESIGN-SYSTEM.md §6). They draw values the
// exporter already counted; nothing here computes a clinical number.

import { useNavigate } from 'react-router-dom';
import type { Cohort, PatientView, Severity } from '../data/contract';
import { SEVERITY_LABEL, SEVERITY_TONE } from '../data/format';

export const TOP_TONE: Record<Severity | 'none', string> = { ...SEVERITY_TONE, none: 'var(--ok)' };
export const TOP_LABEL: Record<Severity | 'none', string> = { ...SEVERITY_LABEL, none: 'No issue found' };

/** One square per patient, most urgent first, coloured by the most severe submitted alert. Click opens the patient. */
export function SeverityMap({ order, byId, size = 7, gap = 2 }: { order: string[]; byId: Map<string, PatientView>; size?: number; gap?: number }) {
  const navigate = useNavigate();
  const cols = 100;
  const rows = Math.ceil(order.length / cols);
  const step = size + gap;
  return (
    <svg viewBox={`0 0 ${cols * step} ${rows * step}`} width="100%" role="img" style={{ display: 'block' }}
      aria-label={`Every patient as one square, most urgent first; ${order.length} patients. Select a square to open the patient.`}
      onClick={(e) => { const id = (e.target as SVGElement).getAttribute('data-id'); if (id) navigate(`/app/patient/${id}`); }}>
      {order.map((id, i) => {
        const top = byId.get(id)?.compare.medsafe.top_severity ?? 'none';
        return (
          <rect key={id} data-id={id} x={(i % cols) * step} y={Math.floor(i / cols) * step} width={size} height={size}
            fill={TOP_TONE[top]} style={{ cursor: 'pointer' }}>
            <title>{`${id}: ${TOP_LABEL[top]}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

/** Vertical bars with their counts above them. */
export function Bars({ items, height = 96, label }: { items: { label: string; value: number; color: string; title?: string }[]; height?: number; label: string }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  const W = items.length * 48, top = 16, bottom = 18, plot = height - top - bottom;
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" role="img" aria-label={label} style={{ display: 'block', maxWidth: W * 1.6 }}>
      {items.map((it, i) => {
        const h = Math.max(1, (it.value / max) * plot);
        return (
          <g key={it.label}>
            <rect x={i * 48 + 8} y={top + plot - h} width={32} height={h} fill={it.color}><title>{it.title ?? `${it.label}: ${it.value}`}</title></rect>
            <text x={i * 48 + 24} y={top + plot - h - 4} textAnchor="middle" fontSize={10} fontFamily="var(--mono)" fill="var(--ink-2)">{it.value}</text>
            <text x={i * 48 + 24} y={height - 4} textAnchor="middle" fontSize={10} fontFamily="var(--mono)" fill="var(--ink-3)">{it.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** Two bars per group, labelled inline on the first group only (H4-DESIGN.md §7). */
export function GroupedBars({ groups, series, label, digits = 2 }: {
  groups: { label: string; a: number; b: number }[]; series: [string, string]; label: string; digits?: number;
}) {
  const W = 640, H = 240, left = 40, right = 16, top = 24, bottom = 44;
  const max = Math.max(...groups.flatMap((g) => [g.a, g.b])) || 1;
  const nice = Math.ceil(max * 10) / 10;
  const plotH = H - top - bottom;
  const y = (v: number) => top + plotH - (v / nice) * plotH;
  const groupW = (W - left - right) / groups.length, barW = 44;
  const ticks = [0, nice / 2, nice];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={label} style={{ display: 'block', maxWidth: W }}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} stroke="var(--hairline)" />
          <text x={left - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--ink-3)" fontFamily="var(--mono)">{t.toFixed(digits)}</text>
        </g>
      ))}
      {groups.map((g, i) => {
        const cx = left + groupW * i + groupW / 2, xa = cx - barW - 4, xb = cx + 4;
        return (
          <g key={g.label}>
            <rect x={xa} y={y(g.a)} width={barW} height={y(0) - y(g.a)} fill="var(--critical)" />
            <rect x={xb} y={y(g.b)} width={barW} height={y(0) - y(g.b)} fill="var(--action)" />
            <text x={xa + barW / 2} y={y(g.a) - 6} textAnchor="middle" fontSize={11} fill="var(--ink-2)" fontFamily="var(--mono)">{g.a.toFixed(digits)}</text>
            <text x={xb + barW / 2} y={y(g.b) - 6} textAnchor="middle" fontSize={11} fill="var(--ink)" fontFamily="var(--mono)">{g.b.toFixed(digits)}</text>
            {i === 0 && (
              <>
                <text x={xa + barW / 2} y={y(0) + 14} textAnchor="middle" fontSize={10} fill="var(--critical)">{series[0]}</text>
                <text x={xb + barW / 2} y={y(0) + 14} textAnchor="middle" fontSize={10} fill="var(--action)">{series[1]}</text>
              </>
            )}
            <text x={cx} y={H - 8} textAnchor="middle" fontSize={12} fill="var(--ink)" fontWeight={500}>{g.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** One bar split into labelled segments, with a legend underneath. */
export function StackedBar({ segments, label, height = 14 }: { segments: { name: string; value: number; color: string }[]; label: string; height?: number }) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div role="img" aria-label={label}>
      <div className="stacked-bar" style={{ height }}>
        {segments.map((s) => s.value > 0 && <span key={s.name} style={{ width: `${(s.value / total) * 100}%`, background: s.color }} title={`${s.name}: ${s.value}`} />)}
      </div>
      <div className="legend">
        {segments.map((s) => <span key={s.name}><span className="sw" style={{ background: s.color }} />{s.name} <span className="mono">{s.value}</span></span>)}
      </div>
    </div>
  );
}

const GROUP_TONE = { exact: 'var(--ok)', approximate: 'var(--action)', abstained: 'var(--warn)' } as const;

/** How sure each name match was: columns stacked by how the line was matched. */
export function ConfidenceHistogram({ h }: { h: Cohort['confidence_histogram'] }) {
  const groups = ['exact', 'approximate', 'abstained'] as const;
  const totals = h.counts.exact.map((_, i) => groups.reduce((s, g) => s + h.counts[g][i], 0));
  const max = Math.max(1, ...totals);
  const W = 560, H = 160, top = 8, bottom = 22, plot = H - top - bottom;
  const colW = W / totals.length;
  const below = groups.reduce((s, g) => s + (h.below_first[g] ?? 0), 0);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ display: 'block' }}
        aria-label={`Confidence of every name match, from ${h.edges[0]} to ${h.edges[h.edges.length - 1]}, stacked by how it matched`}>
        {totals.map((_, i) => {
          let yTop = top + plot;
          return (
            <g key={i}>
              {groups.map((g) => {
                const v = h.counts[g][i];
                if (!v) return null;
                const hh = Math.max(1, (Math.sqrt(v) / Math.sqrt(max)) * plot);
                yTop -= hh;
                return <rect key={g} x={i * colW + 2} y={yTop} width={colW - 4} height={hh} fill={GROUP_TONE[g]}><title>{`${h.edges[i].toFixed(2)}–${h.edges[i + 1].toFixed(2)}, ${g}: ${v}`}</title></rect>;
              })}
            </g>
          );
        })}
        {[0, Math.floor(totals.length / 2), totals.length].map((i) => (
          <text key={i} x={Math.min(i * colW, W - 2)} y={H - 6} textAnchor={i === 0 ? 'start' : i === totals.length ? 'end' : 'middle'} fontSize={10} fontFamily="var(--mono)" fill="var(--ink-3)">{h.edges[i].toFixed(2)}</text>
        ))}
      </svg>
      <div className="legend">
        {groups.map((g) => <span key={g}><span className="sw" style={{ background: GROUP_TONE[g] }} />{g}</span>)}
        {below > 0 && <span className="ink-3">and <span className="mono">{below}</span> below {h.edges[0].toFixed(2)}</span>}
        <span className="ink-3">column height is the square root of the count</span>
      </div>
    </div>
  );
}

/** eGFR on a 0–120 scale with the KDIGO category boundaries from the export, and the patient marked. */
export function EgfrGauge({ value, stages, width = 220 }: { value: number; stages: Cohort['egfr_stages']; width?: number }) {
  const max = 120;
  const x = (v: number) => `${(Math.min(v, max) / max) * 100}%`;
  const bounds = stages.filter((s) => s.code && s.from).map((s) => s.from as number);
  return (
    <span className="gauge" style={{ width }} role="img" aria-label={`eGFR ${value} on a scale of 0 to ${max}`}>
      <span className="gauge-track">
        {bounds.map((b) => <span key={b} className="gauge-tick" style={{ left: x(b) }} />)}
        <span className="gauge-mark" style={{ left: x(value) }} />
      </span>
      <span className="gauge-scale">{[0, ...bounds.slice().reverse(), max].map((t) => <span key={t} style={{ left: x(t) }}>{t}</span>)}</span>
    </span>
  );
}
