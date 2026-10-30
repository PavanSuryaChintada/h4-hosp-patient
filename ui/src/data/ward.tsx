// The ward's local server (tools/serve_ui.py). It runs the real pipeline on each hand-entered
// patient and enforces medsafe.workflow; the browser only sends what a person typed.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useAuth } from '../auth';
import type { WardRecord, WardRow, WardTask } from './contract';

export const SERVE_COMMAND = 'python tools/serve_ui.py';
export const DEMO_COMMAND = 'demo.cmd';

export class WardError extends Error {}

export async function api<T>(path: string, body?: object): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/${path}`, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
  } catch {
    throw new WardError(`The ward server is not running. Start it with ${DEMO_COMMAND} or ${SERVE_COMMAND}.`);
  }
  // A static host answers /api/... with its own page, not the ward's JSON: that is "not running here".
  if (!(response.headers.get('content-type') ?? '').includes('application/json')) {
    throw new WardError(`The ward server is not running here. Start it with ${DEMO_COMMAND} or ${SERVE_COMMAND}.`);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new WardError(data?.error ?? `The ward server answered ${response.status}.`);
  return data as T;
}

/** The signed-in person as the server records them, or null for a role the ward does not know. */
export function useActor() {
  const { user } = useAuth();
  return useMemo(() => (user && user.key !== 'reviewer' ? { user: user.name, role: user.key } : null), [user]);
}

type WardLive = { up: boolean | null; rows: WardRow[] | null; refresh: () => Promise<void> };
const WardContext = createContext<WardLive>({ up: null, rows: null, refresh: async () => {} });

/**
 * Whether the ward server answers, and every record's summary row, re-read every few seconds so
 * one role sees what another just did. Slower while the server is down.
 */
export function WardProvider({ children }: { children: ReactNode }) {
  const [up, setUp] = useState<boolean | null>(null);
  const [rows, setRows] = useState<WardRow[] | null>(null);
  const refresh = useCallback(async () => {
    try { setRows(await api<WardRow[]>('records')); setUp(true); } catch { setUp(false); }
  }, []);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, up ? 4000 : 15000);
    return () => clearInterval(timer);
  }, [refresh, up]);
  const value = useMemo(() => ({ up, rows, refresh }), [up, rows, refresh]);
  return <WardContext.Provider value={value}>{children}</WardContext.Provider>;
}

export function useWard(): WardLive {
  return useContext(WardContext);
}

/** Whether the ward server answers. `null` while checking. */
export function useWardUp(): boolean | null {
  return useWard().up;
}

export type MyTask = WardTask & { record: string };

/** The signed-in role's tasks across the ward, oldest record first. */
export function useMyTasks(): MyTask[] {
  const { rows } = useWard();
  const { user } = useAuth();
  return useMemo(() => (rows ?? []).slice().reverse()
    .flatMap((r) => r.tasks.filter((t) => t.role === user?.key).map((t) => ({ ...t, record: r.id }))), [rows, user]);
}

/** One ward record, re-read after every change the server accepts. `send` returns the new record, or null. */
export function useRecord(id: string) {
  const { refresh } = useWard();
  const [record, setRecord] = useState<WardRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    api<WardRecord>(`records/${id}`).then(setRecord).catch((e: Error) => setError(e.message));
  }, [id]);
  useEffect(reload, [reload]);
  const send = useCallback(async (action: string, body: object): Promise<WardRecord | null> => {
    setError(null);
    try {
      const next = await api<WardRecord>(`records/${id}/${action}`, body);
      setRecord(next);
      refresh();
      return next;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, [id, refresh]);
  return { record, error, send, setError, reload };
}
