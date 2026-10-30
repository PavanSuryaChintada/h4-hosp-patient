// Loads the pipeline's UI data file once and hands it to every screen.
// The file is served from the app's own origin (public/data/), so it works with the network off.

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { SCHEMA_VERSION, type Export, type Medication, type PatientView } from './contract';

export type Data = {
  x: Export;
  byId: Map<string, PatientView>;
  /** Written line (lineKey) -> how the pipeline resolved it, and on which patient it was seen. */
  lines: Map<string, { med: Medication; patient: string }>;
  /** A whole list (sorted line keys) -> the patient whose list it is. */
  lists: Map<string, string>;
};

/** How the scorer identifies a written line. Mirrors token_key in src/medsafe/output/writer.py. */
export function lineKey(text: string): string {
  return text.normalize('NFKC').replace(/[​‌‍⁠﻿­]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
}

export function listKey(lines: string[]): string {
  return lines.map(lineKey).sort().join('\n');
}

function index(x: Export): Data {
  const byId = new Map(x.patients.map((p) => [p.id, p]));
  const lines = new Map<string, { med: Medication; patient: string }>();
  const lists = new Map<string, string>();
  for (const p of x.patients) {
    for (const m of p.medications) if (!lines.has(lineKey(m.raw))) lines.set(lineKey(m.raw), { med: m, patient: p.id });
    lists.set(listKey(p.medications.map((m) => m.raw)), p.id);
  }
  return { x, byId, lines, lists };
}

const DataContext = createContext<Data | null>(null);
type State = { status: 'loading' } | { status: 'failed'; reason: string } | { status: 'ready'; data: Data };

export function DataProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: 'loading' });

  useEffect(() => {
    let live = true;
    fetch(`${import.meta.env.BASE_URL}data/pipeline.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((x: Export) => {
        if (x.schema_version !== SCHEMA_VERSION) throw new Error(`schema ${x.schema_version}, this build reads ${SCHEMA_VERSION}`);
        if (live) setState({ status: 'ready', data: index(x) });
      })
      .catch((e: Error) => { if (live) setState({ status: 'failed', reason: e.message }); });
    return () => { live = false; };
  }, []);

  if (state.status === 'loading') return <div className="boot">Reading pipeline output</div>;
  if (state.status === 'failed') {
    return (
      <div className="boot">
        <p>Could not read <span className="mono">public/data/pipeline.json</span> ({state.reason}).</p>
        <p>Generate it from the repo root with <span className="mono">python tools/export_ui.py</span>.</p>
      </div>
    );
  }
  return <DataContext.Provider value={state.data}>{children}</DataContext.Provider>;
}

export function useData(): Data {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used inside DataProvider');
  return ctx;
}
