// Toasts: what just happened, in the colour of what it means. They float (the one place a shadow
// is allowed), stack top right, and leave on their own; a serious new alert stays longer.

import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Icon, type IconName } from './viz';

/**
 * done: something finished (ok). turn: it is someone's turn now (accent). wait: waiting on
 * someone, or needs a check (warn). handed: with the pharmacist (unknown). danger: a serious
 * alert in the data (critical). fail: the request did not go through (grey, never red).
 */
export type Tone = 'done' | 'turn' | 'wait' | 'handed' | 'danger' | 'fail';
export type ToastInput = { tone: Tone; title: string; body?: ReactNode; link?: { to: string; label: string } };
type Item = ToastInput & { id: number };

const ICON: Record<Tone, IconName> = { done: 'check', turn: 'arrow', wait: 'clock', handed: 'pill', danger: 'alert', fail: 'x' };
const LIFE: Record<Tone, number> = { done: 5000, turn: 6000, wait: 6000, handed: 6000, danger: 10000, fail: 8000 };

const ToastContext = createContext<(t: ToastInput) => void>(() => {});
let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((t) => t.id !== id)), []);
  const push = useCallback((t: ToastInput) => {
    const id = ++seq;
    setItems((xs) => [...xs.slice(-2), { ...t, id }]);
    setTimeout(() => dismiss(id), LIFE[t.tone]);
  }, [dismiss]);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast tone-${t.tone}`}>
            <span className="toast-icon" aria-hidden="true"><Icon name={ICON[t.tone]} size={16} /></span>
            <div className="toast-text">
              <strong>{t.title}</strong>
              {t.body && <span>{t.body}</span>}
              {t.link && <Link to={t.link.to} onClick={() => dismiss(t.id)}>{t.link.label} →</Link>}
            </div>
            <button type="button" className="toast-x" aria-label="Dismiss" onClick={() => dismiss(t.id)}><Icon name="x" size={14} /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
