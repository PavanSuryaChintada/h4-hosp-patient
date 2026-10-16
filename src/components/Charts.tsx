/** Grouped bar: two bars per group, labelled inline on the first group only. */
export function GroupedBars({ groups, seriesLabels }: {
  groups: { label: string; a: number; b: number }[];
  seriesLabels: [string, string];
}) {
  const W = 600, H = 240, left = 40, right = 16, top = 24, bottom = 48;
  const max = Math.max(...groups.flatMap((g) => [g.a, g.b]));
  const niceMax = Math.ceil(max / 10) * 10;
  const plotH = H - top - bottom;
  const y = (v: number) => top + plotH - (v / niceMax) * plotH;
  const groupW = (W - left - right) / groups.length;
  const barW = 48;
  const ticks = [0, niceMax / 2, niceMax];

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" style={{ display: 'block', maxWidth: W }}
      aria-label={groups.map((g) => `${g.label}: ${g.a} ${seriesLabels[0]}, ${g.b} ${seriesLabels[1]}`).join('; ')}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} stroke="var(--hairline)" />
          <text x={left - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--ink-3)" fontFamily="var(--mono)">{t}</text>
        </g>
      ))}
      {groups.map((g, i) => {
        const cx = left + groupW * i + groupW / 2;
        const xa = cx - barW - 4, xb = cx + 4;
        return (
          <g key={g.label}>
            <rect x={xa} y={y(g.a)} width={barW} height={y(0) - y(g.a)} fill="var(--ink-3)" />
            <rect x={xb} y={y(g.b)} width={barW} height={Math.max(y(0) - y(g.b), 0)} fill="var(--action)" />
            <text x={xa + barW / 2} y={y(g.a) - 6} textAnchor="middle" fontSize={11} fill="var(--ink-2)" fontFamily="var(--mono)">{g.a}</text>
            <text x={xb + barW / 2} y={y(g.b) - 6} textAnchor="middle" fontSize={11} fill="var(--ink)" fontFamily="var(--mono)">{g.b}</text>
            {i === 0 && (
              <>
                <text x={xa + barW / 2} y={y(0) + 16} textAnchor="middle" fontSize={11} fill="var(--ink-3)">{seriesLabels[0]}</text>
                <text x={xb + barW / 2} y={y(0) + 16} textAnchor="middle" fontSize={11} fill="var(--action)">{seriesLabels[1]}</text>
              </>
            )}
            <text x={cx} y={H - 12} textAnchor="middle" fontSize={12} fill="var(--ink)" fontWeight={500}>{g.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** The four-step pipeline. */
export function MethodDiagram() {
  const steps = [
    ['Resolve names', 'Raw slip text to a generic.', 'Abstain when unsure.'],
    ['Check rules', 'Interactions, duplicates,', 'renal dose, pregnancy.'],
    ['Re-score in context', 'Same flag, different patient:', 'eGFR, age, weight.'],
    ['Collapse and cap', 'One change per cluster.', 'At most 5 alerts.'],
  ];
  const W = 680, boxW = 152, gap = 24, H = 104;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" style={{ display: 'block', marginTop: 24 }}
      aria-label="Four steps: resolve names, check rules, re-score in patient context, collapse and cap.">
      <defs>
        <marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="var(--ink-3)" />
        </marker>
      </defs>
      {steps.map(([title, l1, l2], i) => {
        const x = i * (boxW + gap);
        return (
          <g key={title}>
            <rect x={x + 0.5} y={0.5} width={boxW - 1} height={H - 1} fill="var(--paper)" stroke="var(--hairline-firm)" />
            {i === 3 && <rect x={x} y={0} width={3} height={H} fill="var(--action)" />}
            <text x={x + 12} y={24} fontSize={11} fill="var(--ink-3)" fontFamily="var(--mono)">{String(i + 1).padStart(2, '0')}</text>
            <text x={x + 12} y={48} fontSize={13} fontWeight={600} fill="var(--ink)">{title}</text>
            <text x={x + 12} y={72} fontSize={11} fill="var(--ink-2)">{l1}</text>
            <text x={x + 12} y={88} fontSize={11} fill="var(--ink-2)">{l2}</text>
            {i < 3 && <line x1={x + boxW + 2} y1={H / 2} x2={x + boxW + gap - 3} y2={H / 2} stroke="var(--ink-3)" markerEnd="url(#arr)" />}
          </g>
        );
      })}
    </svg>
  );
}
