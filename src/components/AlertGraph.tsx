import { DRUG } from '../data/drugs';
import { name, type Analysis } from '../data/engine';

/**
 * Drugs as nodes, interactions as edges. Fixed positions on an ellipse — no force
 * simulation, so nodes never move between renders.
 * `removed` shows the graph after the anchor drug is stopped.
 */
export function AlertGraph({ analysis, width = 440, height = 260, removed = false }: {
  analysis: Analysis; width?: number; height?: number; removed?: boolean;
}) {
  const { generics, edges, anchors, patient } = analysis;
  const anchor = anchors[0];
  const order = anchor ? [anchor, ...generics.filter((g) => g !== anchor)] : generics;
  const unresolved = patient.meds.filter((m) => !m.code);
  const total = order.length + unresolved.length;

  const compact = width < 440;
  const cx = width / 2, cy = height / 2;
  const rx = compact ? width / 2 - 80 : 120, ry = (height / 2) - 40;
  const short = (g: string) => DRUG[g].name.replace(/ \+.*$/, '');
  const pos = (i: number) => {
    const t = -Math.PI / 2 + (i / total) * Math.PI * 2;
    return { x: cx + rx * Math.cos(t), y: cy + ry * Math.sin(t), cos: Math.cos(t), sin: Math.sin(t) };
  };
  const at: Record<string, ReturnType<typeof pos>> = {};
  order.forEach((g, i) => { at[g] = pos(i); });

  const serious = edges.filter((e) => e.severity === 'high');
  const shown = removed ? edges.filter((e) => e.a !== anchor && e.b !== anchor) : edges;
  const cleared = anchor ? serious.filter((e) => e.a === anchor || e.b === anchor).length : 0;

  const aria = anchor
    ? `Alert graph: ${order.length} drugs, ${serious.length} serious interactions. Stopping ${name(anchor)} clears ${cleared} of them.`
    : `Alert graph: ${order.length} drugs, ${serious.length} serious interactions. No single drug anchors a cluster.`;

  const label = (x: number, y: number, cos: number, sin: number, text: string, mono = false, color = 'var(--ink-2)') => {
    const off = 18;
    const anchorText = cos > 0.3 ? 'start' : cos < -0.3 ? 'end' : 'middle';
    const dy = sin > 0.3 ? 8 : sin < -0.3 ? 0 : 4;
    return (
      <text x={x + cos * off} y={y + sin * off + dy} textAnchor={anchorText}
        fontSize={11} fill={color} fontFamily={mono ? 'var(--mono)' : 'var(--sans)'}>{text}</text>
    );
  };

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={aria} style={{ display: 'block', maxWidth: width, overflow: 'visible' }}>
      {shown.map((e) => {
        const p = at[e.a], q = at[e.b];
        const isSerious = e.severity === 'high';
        const onAnchor = !removed && (e.a === anchor || e.b === anchor) && isSerious;
        return (
          <line key={e.rule + e.a + e.b} x1={p.x} y1={p.y} x2={q.x} y2={q.y}
            stroke={isSerious ? 'var(--critical)' : 'var(--ink-3)'}
            strokeOpacity={isSerious ? 1 : 0.55}
            strokeWidth={onAnchor ? 2.5 : isSerious ? 1.5 : 1}>
            <title>{`${name(e.a)} + ${name(e.b)} (${e.severity})`}</title>
          </line>
        );
      })}
      {order.map((g) => {
        const p = at[g];
        const chosen = g === anchor;
        const gone = removed && chosen;
        return (
          <g key={g}>
            <circle cx={p.x} cy={p.y} r={11}
              fill={chosen && !gone ? 'var(--critical)' : 'var(--paper)'}
              stroke={gone ? 'var(--ink-3)' : chosen ? 'var(--critical)' : 'var(--action)'}
              strokeWidth={1.3} strokeDasharray={gone ? '3 2' : undefined} />
            <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize={9} fontFamily="var(--mono)" fontWeight={500}
              fill={chosen && !gone ? '#fff' : gone ? 'var(--ink-3)' : 'var(--ink)'}>{g}</text>
            {label(p.x, p.y, p.cos, p.sin, gone ? `${short(g)} (stopped)` : short(g), false, chosen && !gone ? 'var(--critical)' : gone ? 'var(--ink-3)' : 'var(--ink-2)')}
          </g>
        );
      })}
      {unresolved.map((m, i) => {
        const p = pos(order.length + i);
        return (
          <g key={m.raw}>
            <circle cx={p.x} cy={p.y} r={11} fill="var(--paper)" stroke="var(--warn)" strokeWidth={1.3} strokeDasharray="3 2" />
            <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize={9} fontFamily="var(--mono)" fill="var(--warn)">?</text>
            {label(p.x, p.y, p.cos, p.sin, compact ? 'unchecked' : `"${m.raw}" unchecked`, true, 'var(--warn)')}
          </g>
        );
      })}
    </svg>
  );
}
