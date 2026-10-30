// Decisions on training-set patients, for the hosted demo. There is no ward server there, so
// each accept, override or deferral is kept in this browser, in the same shape as the ward's
// audit log. Ward patients record theirs on the ward server, which enforces medsafe.workflow.

import { useCallback, useMemo, useState } from 'react';
import { store, type DemoUser } from '../auth';
import type { AlertEvent, AuditEvent } from './contract';
import type { Decisions } from '../components/Medsafe';

const KEY = 'medsafe.decisions';

function readAll(): AuditEvent[] {
  try { return JSON.parse(store.get(KEY) ?? '[]') as AuditEvent[]; } catch { return []; }
}

export function useLocalDecisions(patient: string, user: DemoUser | null): Decisions {
  const [all, setAll] = useState<AuditEvent[]>(readAll);
  const states = useMemo(() => {
    const out: Record<string, AuditEvent> = {};
    for (const e of all) if (e.patient_id === patient && e.event !== 'shown') out[e.alert] = e;
    return out;
  }, [all, patient]);
  const onEvent = useCallback(async (alert: string, event: AlertEvent, reason?: string, note?: string) => {
    if (!user || user.key === 'reviewer') return false;
    const next = [...readAll(), {
      timestamp: new Date().toISOString(), user: user.name, role: user.key, patient_id: patient, alert, event,
      reason: reason || null, note: note?.trim() || null,
    } as AuditEvent];
    store.set(KEY, JSON.stringify(next));
    setAll(next);
    return true;
  }, [patient, user]);
  return { states, onEvent, local: true };
}
