// The ward's local server (tools/serve_ui.py). It runs the real pipeline on each hand-entered
// patient and enforces medsafe.workflow; the browser only sends what a person typed.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth';
import type { WardRecord } from './contract';

export const SERVE_COMMAND = 'python tools/serve_ui.py';

export class WardError extends Error {}

export async function api<T>(path: string, body?: object): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/${path}`, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
  } catch {
    throw new WardError(`The ward server is not running. Start it with ${SERVE_COMMAND}.`);
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

/** Whether the ward server answers. `null` while checking. */
export function useWardUp(): boolean | null {
  const [up, setUp] = useState<boolean | null>(null);
  useEffect(() => {
    let live = true;
    api('health').then(() => live && setUp(true)).catch(() => live && setUp(false));
    return () => { live = false; };
  }, []);
  return up;
}

/** One ward record, re-read after every change the server accepts. */
export function useRecord(id: string) {
  const [record, setRecord] = useState<WardRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<WardRecord>(`records/${id}`).then(setRecord).catch((e: Error) => setError(e.message));
  }, [id]);
  const send = useCallback(async (action: string, body: object) => {
    setError(null);
    try { setRecord(await api<WardRecord>(`records/${id}/${action}`, body)); return true; } catch (e) {
      setError((e as Error).message);
      return false;
    }
  }, [id]);
  return { record, error, send, setError };
}
