// Pharmacist-review handoffs. The human in the loop: a prescriber flags a patient and the flag
// is recorded with who and when. There is no backend, so the record lives in this browser.

import { useCallback, useState } from 'react';
import { store } from '../auth';

export type Handoff = { patient: string; at: string; by: string; role: string; note: string };

const KEY = 'medsafe.handoffs';

function readAll(): Handoff[] {
  try { return JSON.parse(store.get(KEY) ?? '[]') as Handoff[]; } catch { return []; }
}

export function useHandoffs(patient: string) {
  const [all, setAll] = useState<Handoff[]>(readAll);
  const record = useCallback((h: Omit<Handoff, 'patient' | 'at'>) => {
    const next = [...readAll(), { ...h, patient, at: new Date().toISOString() }];
    store.set(KEY, JSON.stringify(next));
    setAll(next);
  }, [patient]);
  return { handoffs: all.filter((h) => h.patient === patient), record };
}
