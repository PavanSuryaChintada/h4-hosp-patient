import type { Severity } from '../data/contract';
import { SEVERITY_TONE } from '../data/format';

type Tier = { egfr_below: number; severity: Severity };
type Mark = { label: string; egfr: number };

/**
 * A drug's renal tiers from renal_rules.csv, drawn on an eGFR axis, with each patient's value
 * marked. Draws the reference table and the recorded values; it decides nothing.
 */
export function TierLadder({ generic, ladder, marks, width = 560 }: { generic: string; ladder: Tier[]; marks: Mark[]; width?: number }) {
  const tiers = [...ladder].sort((a, b) => a.egfr_below - b.egfr_below);
  const top = Math.max(120, ...marks.map((m) => m.egfr + 10));
  const left = 8, right = 8, barY = 40, barH = 16, H = 112;
  const x = (v: number) => left + (Math.min(v, top) / top) * (width - left - right);
  const zones = tiers.map((t, i) => ({ from: i === 0 ? 0 : tiers[i - 1].egfr_below, to: t.egfr_below, severity: t.severity }));
  const ticks = [0, ...tiers.map((t) => t.egfr_below), top];

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${H}`} role="img" style={{ display: 'block', maxWidth: width }}
      aria-label={`${generic} renal tiers: ${tiers.map((t) => `eGFR below ${t.egfr_below}, ${t.severity}`).join('; ')}. ${marks.map((m) => `${m.label} at eGFR ${m.egfr}`).join('; ')}.`}>
      <rect x={x(0)} y={barY} width={x(top) - x(0)} height={barH} fill="var(--sunken)" />
      {/* Each band covers only its own range: below the lowest threshold the most restrictive tier is the one that applies. */}
      {zones.map((z) => (
        <g key={z.to}>
          <rect x={x(z.from)} y={barY} width={x(z.to) - x(z.from)} height={barH} fill={SEVERITY_TONE[z.severity]} opacity={0.25} />
          <text x={(x(z.from) + x(z.to)) / 2} y={barY + barH + 16} textAnchor="middle" fontSize={11} fill={SEVERITY_TONE[z.severity]} fontWeight={500}>
            {`< ${z.to}: ${z.severity}`}
          </text>
        </g>
      ))}
      {ticks.map((t, i) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={barY - 4} y2={barY + barH} stroke="var(--hairline-firm)" />
          <text x={x(t)} y={barY - 8} textAnchor={i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'}
            fontSize={11} fill="var(--ink-3)" fontFamily="var(--mono)">{t}</text>
        </g>
      ))}
      {marks.map((m, i) => (
        <g key={m.label}>
          <line x1={x(m.egfr)} x2={x(m.egfr)} y1={barY - 2} y2={barY + barH + 2} stroke="var(--ink)" strokeWidth={3} />
          <text x={x(m.egfr)} y={i % 2 ? H - 4 : barY + barH + 32} textAnchor="middle" fontSize={11} fill="var(--ink)" fontFamily="var(--mono)">
            {m.label} · {m.egfr}
          </text>
        </g>
      ))}
    </svg>
  );
}
