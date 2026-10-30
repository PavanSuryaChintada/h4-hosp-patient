import { useMemo, useState } from 'react';
import type { Medication, Method } from '../data/contract';
import { METHOD_LABEL, METHOD_TAG, conf, pct } from '../data/format';
import { useData } from '../data/load';
import { Kpi } from '../components/viz';
import { PatientLink, Segmented } from '../components/ui';
import { ConfidenceHistogram, StackedBar } from '../components/Charts';

type Filter = 'all' | Method | 'mismatch';
const ORDER: Method[] = ['exact', 'synonym', 'parts', 'prefix', 'fuzzy', 'non_drug', 'abstained'];
const PAGE = 100;
const METHOD_COLOR: Record<Method, string> = {
  exact: 'var(--ok)', synonym: 'var(--ok)', parts: 'var(--action)', prefix: 'var(--action)', fuzzy: 'var(--action)',
  non_drug: 'var(--hairline-firm)', abstained: 'var(--warn)',
};

function LabelCheck({ m }: { m: Medication }) {
  if (!m.truth) return <span className="ink-3">no label</span>;
  if (m.truth.match) return <span className="ink-3">matches</span>;
  return <span style={{ color: 'var(--critical)' }}>label: {m.truth.generics?.join(' ; ') || 'not a medicine'}</span>;
}

export function Resolution() {
  const { x } = useData();
  const [filter, setFilter] = useState<Filter>('all');
  const [shown, setShown] = useState(PAGE);
  const r = x.resolution;
  const split = x.evaluation.report?.splits.holdout;
  const dev = x.evaluation.report?.splits.dev;

  const all = useMemo(() => x.patients.flatMap((p) => p.medications.map((m) => ({ id: p.id, m }))), [x.patients]);
  const rows = useMemo(() => all.filter(({ m }) => filter === 'all'
    || (filter === 'mismatch' ? m.truth !== null && !m.truth.match : m.method === filter)), [all, filter]);

  return (
    <div className="content">
      <div className="page-head">
        <h1 className="display">Name resolution</h1>
        <p className="meta">Every line in the {x.source.split} split, exactly as written, and what the pipeline resolved it to.</p>
      </div>

      <div className="kpis kpis-3">
        <Kpi label="Accuracy on misspelled lines, holdout split"
          value={split ? pct(split.resolution.misspelled_accuracy) : <span className="kpi-of">no report</span>}
          sub={split ? <>All lines: <span className="mono">{pct(split.resolution.accuracy)}</span> of <span className="mono">{split.resolution.lines}</span>. Dev split, misspelled: <span className="mono">{dev ? pct(dev.resolution.misspelled_accuracy) : '—'}</span>. From <span className="mono">{x.evaluation.path}</span>.</> : x.evaluation.unavailable} />
        <Kpi label="Resolved to the wrong medicine, holdout split"
          value={split ? <>{split.resolution.false_resolutions} <span className="kpi-of">lines</span></> : '—'}
          sub={<>A confident wrong answer is worse than an abstention, so the resolver abstains when two candidates are too close.</>} />
        <Kpi label="Marked for a manual check, all exported lines"
          value={<>{r.by_method.abstained ?? 0} <span className="kpi-of">of {r.lines}</span></>}
          sub={<>Never dropped: shown as "could not resolve, verify manually" wherever the line appears.</>} />
      </div>

      <div className="res-charts">
        <section className="panel">
          <div className="panel-head"><h2 className="section">How each line was matched</h2><span className="meta"><span className="mono">{r.lines.toLocaleString('en-GB')}</span> lines</span></div>
          <div className="results-chart-body">
            <StackedBar label="Lines by how they were matched" segments={ORDER.filter((m) => r.by_method[m]).map((m) => ({ name: METHOD_LABEL[m], value: r.by_method[m] ?? 0, color: METHOD_COLOR[m] }))} />
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><h2 className="section">How sure each match was</h2><span className="meta">every line that names a medicine</span></div>
          <div className="results-chart-body"><ConfidenceHistogram h={x.cohort.confidence_histogram} /></div>
        </section>
      </div>

      <div className="queue-tools">
        <Segmented label="Filter by how the line was resolved" value={filter} onChange={(f) => { setFilter(f); setShown(PAGE); }} segments={[
          { value: 'all', label: 'All', count: r.lines },
          ...ORDER.filter((mth) => r.by_method[mth]).map((mth) => ({ value: mth as Filter, label: METHOD_LABEL[mth], count: r.by_method[mth] })),
          ...(r.label_mismatches !== null ? [{ value: 'mismatch' as Filter, label: 'Label disagrees', count: r.label_mismatches }] : []),
        ]} />
      </div>

      <div className="panel">
        <table className="t">
          <colgroup>
            <col style={{ width: 144 }} /><col style={{ width: 280 }} /><col style={{ width: 280 }} />
            <col style={{ width: 104 }} /><col style={{ width: 168 }} /><col />
          </colgroup>
          <thead>
            <tr><th>Patient</th><th>As written</th><th>Resolved to</th><th className="num">Confidence</th><th>How</th><th>Training label</th></tr>
          </thead>
          <tbody>
            {rows.slice(0, shown).map(({ id, m }) => (
              <tr key={`${id}-${m.index}`}>
                <td><PatientLink id={id} /></td>
                <td className="mono ink-2 cell-clip" title={m.raw}>"{m.raw}"</td>
                <td className="mono cell-clip" style={{ color: m.method === 'abstained' ? 'var(--warn)' : undefined }}>
                  {m.method === 'abstained' ? `could not resolve${m.candidates.length ? `: ${m.candidates.map(([g, s]) => `${g} ${conf(s)}`).join(' / ')}` : ''}`
                    : m.generics.join(' ; ') || <span className="ink-3">not a medicine</span>}
                </td>
                <td className="num">{conf(m.confidence)}</td>
                <td>
                  <span className={`tag ${METHOD_TAG[m.method]}`}>{METHOD_LABEL[m.method]}</span>
                  {m.combination === 'brand' && <span className="tag tag-action" style={{ marginLeft: 4 }}>combination</span>}
                </td>
                <td><LabelCheck m={m} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="empty">No line in this group.</p>}
      </div>
      {rows.length > shown && (
        <div className="more">
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShown((n) => n + PAGE)}>Show {Math.min(PAGE, rows.length - shown)} more</button>
          <span className="meta">Showing <span className="mono">{shown}</span> of <span className="mono">{rows.length}</span></span>
        </div>
      )}
    </div>
  );
}
