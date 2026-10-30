// Where the list comes from. Typed at the desk or pulled through ABHA, it arrives as the same
// messy consolidated list, and that is where the pipeline starts.
//
// "Run check" never runs a model or a rule in the browser. A list that matches an exported
// patient opens that patient's pipeline output; otherwise each line is looked up in the lines
// the pipeline has already resolved, and a line it has not seen says so.

import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth';
import { useData, lineKey, listKey } from '../data/load';
import { plural } from '../data/format';
import { MedRow } from '../components/Medications';
import { Segmented } from '../components/ui';

type Tab = 'typed' | 'abha';

const split = (text: string) => text.split(/[;\n]/).map((s) => s.trim()).filter(Boolean);

function Typed() {
  const { x, byId, lines, lists } = useData();
  const { user } = useAuth();
  const seedId = x.demo?.pins.find((p) => p.slot === 'abstention')?.patient_ids[0] ?? x.patients[0]?.id;
  const seed = seedId ? byId.get(seedId)!.medications.map((m) => m.raw).join('; ') : '';
  const [text, setText] = useState(seed);
  const [ran, setRan] = useState<string | null>(null);

  const result = useMemo(() => {
    if (ran === null) return null;
    const entries = split(ran);
    return {
      entries: entries.map((raw) => ({ raw, hit: lines.get(lineKey(raw)) })),
      patient: lists.get(listKey(entries)) ?? null,
    };
  }, [ran, lines, lists]);
  const unseen = result ? result.entries.filter((e) => !e.hit).length : 0;

  return (
    <div className="intake-grid">
      <section className="panel intake-in">
        <div className="panel-head"><h2 className="section">Medication list</h2><span className="meta">One per line, or separated by ;</span></div>
        <div className="intake-body">
          <label className="field" style={{ marginTop: 0 }}>
            <span className="label">As copied from the slips, strips and bottles</span>
            <textarea rows={12} className="mono" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} />
          </label>
          <div className="intake-actions">
            <button type="button" className="btn btn-primary" onClick={() => setRan(text)}>Run check</button>
            {seedId && <span className="meta">Pre-loaded with patient <span className="mono">{seedId}</span>'s list, exactly as written in the dataset.</span>}
          </div>
        </div>
      </section>

      <section className="panel intake-out" aria-live="polite">
        <div className="panel-head"><h2 className="section">What the pipeline made of it</h2></div>
        {!result ? (
          <p className="empty">Run the check to see each line resolved.</p>
        ) : (
          <>
            <div className="intake-verdict">
              {result.patient ? (
                <p>This list is patient <span className="mono">{result.patient}</span>'s, already run through the pipeline. <Link to={`/app/patient/${result.patient}`}>Open the full check →</Link></p>
              ) : (
                <p>No exported patient has exactly this list. Each line below is looked up in the lines the pipeline has already resolved. This screen never re-implements the rules: to run the full check on a new list, admit it on the ward, where the ward server runs the pipeline.
                  {user?.key === 'nurse' && <> <Link to="/app/ward/new" state={{ medication_list: split(ran ?? '').join('\n') }}>Admit as a new ward patient →</Link></>}</p>
              )}
              {unseen > 0 && <p className="ink-2">{plural(unseen, 'line')} not in the pipeline's output yet, so not resolved here.</p>}
            </div>
            <div className="medlist">
              {result.entries.map((e, i) => e.hit
                ? <MedRow key={i} m={e.hit.med} />
                : (
                  <div key={i} className="medrow unseen">
                    <span className="raw" title={e.raw}>"{e.raw}"</span>
                    <span className="arr" aria-hidden="true">→</span>
                    <span className="res res-none">not in the pre-computed output; run the pipeline to resolve it</span>
                    <span className="cf" /><span />
                  </div>
                ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function Abha() {
  return (
    <section className="panel abha">
      <div className="panel-head"><h2 className="section">ABHA sync</h2><span className="tag tag-grey">No ABDM connection · simulated sandbox on the ward</span></div>
      <div className="abha-body">
        <ol className="abha-steps">
          <li><strong>The patient consents.</strong> ABHA is the patient's health account under the Ayushman Bharat Digital Mission. A hospital asks to see records; the patient approves the request through a consent manager.</li>
          <li><strong>Records are pulled from where they live.</strong> The network is federated: records stay with the clinics and hospitals that created them, and are shared only under that consent. There is no central database of records.</li>
          <li><strong>The list is still messy.</strong> What arrives is written by different prescribers: brand names, abbreviations and misspellings, the same as a list typed at the desk.</li>
          <li><strong>We consume the same consolidated list either way.</strong> One list per patient, one line per medicine, into the same pipeline.</li>
        </ol>
        <p className="meta" style={{ marginTop: 16 }}>
          Try it: sign in as the ward nurse and open <Link to="/app/ward/new">Admit a patient</Link>. The ABHA step there is a sandbox run by the ward server:
          sandbox addresses end in <span className="mono">@sbx</span>, the patient's approval is a button, and the records are synthetic patients from the pack's test split.
          The fetched list lands on the one record the nurse, lab, pharmacist and prescriber all work from.
        </p>
      </div>
    </section>
  );
}

export function Intake() {
  const [tab, setTab] = useState<Tab>('typed');
  return (
    <div className="content">
      <div className="page-head">
        <h1 className="display">Intake</h1>
        <p className="meta">Whether it arrives by digital sync or a nurse typing for 30 seconds, the list is messy in the same way. We start where that list lands.</p>
      </div>
      <Segmented label="How the list arrives" value={tab} onChange={setTab} className="intake-tabs" segments={[
        { value: 'typed', label: 'Typed at the desk' },
        { value: 'abha', label: 'ABHA sync' },
      ]} />
      {tab === 'typed' ? <Typed /> : <Abha />}
    </div>
  );
}
