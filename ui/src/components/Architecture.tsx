// What Medsafe is built from, drawn by hand in SVG on fixed coordinates (no layout engine, no
// chart library). Describes the code in this repository; it holds no numbers.

type Box = { x: number; y: number; w: number; h: number; title: string; lines: string[]; tone?: 'engine' | 'out' | 'side' | 'in' | 'web'; dashed?: boolean };

const W = 1160, H = 640;

const BOXES: Box[] = [
  // inputs
  { x: 16, y: 72, w: 220, h: 112, tone: 'in', title: 'H4 data pack', lines: ['training and test patients', 'reference tables: drugs, combinations,', 'interactions, renal tiers,', 'duplicates, conditions'] },
  { x: 16, y: 208, w: 220, h: 112, tone: 'in', title: 'Ward entry', lines: ['nurse types the list as written', 'ABHA consent pull (sandbox)', 'lab enters eGFR', 'pharmacist confirms names'] },

  // engine steps
  { x: 292, y: 72, w: 236, h: 56, tone: 'engine', title: '1  Load and validate', lines: ['data/adapter.py: bad value, not bad patient'] },
  { x: 292, y: 140, w: 236, h: 84, tone: 'engine', title: '2  Read every line', lines: ['exact, synonym, parts, prefix,', 'fuzzy (rapidfuzz, OSA edits),', 'or abstain: "verify manually"'] },
  { x: 292, y: 236, w: 236, h: 100, tone: 'engine', title: '3  Check the tables', lines: ['current regimen, stopped lines', 'conditions and negation in text', 'interactions, duplicates,', 'renal tiers, contraindications'] },
  { x: 292, y: 348, w: 236, h: 80, tone: 'engine', title: '4  Output policy', lines: ['table severity and action, verbatim', 'minor shown, not submitted', 'confidence and limitations'] },

  // outputs
  { x: 596, y: 72, w: 252, h: 72, tone: 'out', title: 'Track A: submission', lines: ['run.py writes H4_predictions.csv', 'and H4_resolution.csv'] },
  { x: 892, y: 72, w: 252, h: 72, tone: 'out', title: "Organisers' evaluate.py", lines: ['scores the test patients', 'against their hidden answers'] },
  { x: 596, y: 176, w: 252, h: 92, tone: 'out', title: 'Track B: clinician layer', lines: ['prioritise, collapse ("review X first")', 'workflow: roles, permissions,', 'override reasons, audit log'] },
  { x: 596, y: 296, w: 252, h: 76, tone: 'web', title: 'Ward server', lines: ['tools/serve_ui.py, Python http.server', 'runs the pipeline per patient'] },
  { x: 596, y: 392, w: 252, h: 76, tone: 'web', title: 'Export', lines: ['tools/export_ui.py writes', 'pipeline.json for the web app'] },
  { x: 892, y: 296, w: 252, h: 172, tone: 'web', title: 'Web app', lines: ['React 18, TypeScript, Vite', 'hand-drawn SVG, IBM Plex', 'reads pipeline.json and the', 'ward server; computes nothing', 'GitHub Pages and Vercel', '(the ward runs locally)'] },

  // off the scoring path
  { x: 16, y: 512, w: 1128, h: 96, tone: 'side', dashed: true, title: 'Off the scoring path: evaluation and experiments (eval/)', lines: [
    "dev / holdout split of the 1,500 training patients, scored by the organisers' evaluate.py, with every near-miss traced  ·  a standard EHR check reproduced from the same tables (tools/ehr_reference.py)",
    'three trained models measured against the rules: n-gram TF-IDF nearest neighbour (names), logistic regression (conditions), gradient-boosted trees (alert triage)  ·  graphs with matplotlib',
  ] },
];

const ARROWS: [number, number, number, number][] = [
  [236, 128, 292, 100], [236, 264, 292, 280],          // inputs -> engine
  [410, 128, 410, 140], [410, 224, 410, 236], [410, 336, 410, 348],   // engine steps
  [528, 384, 596, 108], [528, 384, 596, 222],          // policy -> tracks
  [848, 108, 892, 108],                                  // submission -> evaluate.py
  [722, 268, 722, 296], [722, 372, 722, 392],           // clinician layer -> server -> export
  [848, 334, 892, 334], [848, 430, 892, 430],           // server, export -> web app
];

const TONE: Record<NonNullable<Box['tone']>, { fill: string; stroke: string; bar: string }> = {
  in: { fill: 'var(--sunken)', stroke: 'var(--hairline-firm)', bar: 'var(--ink-3)' },
  engine: { fill: 'var(--paper)', stroke: 'var(--action)', bar: 'var(--action)' },
  out: { fill: 'var(--paper)', stroke: 'var(--hairline-firm)', bar: 'var(--ok)' },
  web: { fill: 'var(--paper)', stroke: 'var(--hairline-firm)', bar: 'var(--action)' },
  side: { fill: 'var(--canvas)', stroke: 'var(--hairline-firm)', bar: 'var(--ink-3)' },
};

export function Architecture() {
  return (
    <figure className="arch-fig">
      <div className="arch-scroll">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ display: 'block', minWidth: 880 }}
          aria-label="Architecture. Inputs: the H4 data pack and ward entry (nurse, ABHA sandbox, lab, pharmacist). The Medsafe engine in Python with the standard library and rapidfuzz: load and validate, read every line, check the reference tables, output policy. Track A writes the two submission files that the organisers' evaluate.py scores. Track B, the clinician layer, prioritises and collapses alerts and holds the workflow and audit log; the ward server and the export feed the web app, built in React, TypeScript and Vite. Off the scoring path: evaluation and three trained models measured against the rules. No language model anywhere and no network at runtime.">
          <defs>
            <marker id="arch-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="var(--ink-3)" />
            </marker>
          </defs>

          <text x={16} y={40} fontSize={13} fontWeight={600} fill="var(--ink)">Inputs</text>
          <rect x={276} y={24} width={268} height={412} fill="none" stroke="var(--action)" strokeDasharray="0" />
          <text x={292} y={44} fontSize={13} fontWeight={600} fill="var(--action)">Medsafe engine, src/medsafe</text>
          <text x={292} y={60} fontSize={11} fill="var(--ink-2)">Python 3.11, standard library + rapidfuzz</text>
          <text x={596} y={40} fontSize={13} fontWeight={600} fill="var(--ink)">Two tracks, one engine</text>

          {ARROWS.map(([x1, y1, x2, y2], i) => (
            <line key={i} x1={x1} y1={y1} x2={x2 - 2} y2={y2} stroke="var(--ink-3)" strokeWidth={1.2} markerEnd="url(#arch-arrow)" />
          ))}

          {BOXES.map((b) => {
            const t = TONE[b.tone ?? 'out'];
            return (
              <g key={b.title}>
                <rect x={b.x + 0.5} y={b.y + 0.5} width={b.w - 1} height={b.h - 1} fill={t.fill} stroke={t.stroke} strokeDasharray={b.dashed ? '5 4' : undefined} />
                <rect x={b.x} y={b.y} width={3} height={b.h} fill={t.bar} />
                <text x={b.x + 14} y={b.y + 20} fontSize={12} fontWeight={600} fill="var(--ink)">{b.title}</text>
                {b.lines.map((line, i) => (
                  <text key={i} x={b.x + 14} y={b.y + 38 + i * 16} fontSize={11} fill="var(--ink-2)">{line}</text>
                ))}
              </g>
            );
          })}

          <text x={292} y={460} fontSize={11} fill="var(--ink-2)">No language model anywhere. No network at runtime.</text>
          <text x={292} y={476} fontSize={11} fill="var(--ink-2)">Same input, same output, every run.</text>
        </svg>
      </div>
    </figure>
  );
}
