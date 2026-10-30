// Hardcoded demo accounts. There is no backend: the session is a key in localStorage.

import { createContext, useContext, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

/** `key` is the role the ward server enforces (medsafe.workflow.ROLES); reviewer is read-only. */
export type RoleKey = 'prescriber' | 'pharmacist' | 'nurse' | 'lab' | 'reviewer';
export type DemoUser = { email: string; password: string; name: string; role: string; key: RoleKey; focus: string; home: string };

export const DEMO_USERS: DemoUser[] = [
  { email: 'nurse@medsafe.demo', password: 'Nurse@2026', name: 'Lakshmi Rao', role: 'Ward nurse', key: 'nurse',
    focus: 'Admits patients and copies the medication list exactly as written', home: '/app/ward' },
  { email: 'lab@medsafe.demo', password: 'Lab@2026', name: 'Ravi Kumar', role: 'Lab technician', key: 'lab',
    focus: 'Enters eGFR; the kidney-dose checks re-run on it', home: '/app/ward' },
  { email: 'pharmacist@medsafe.demo', password: 'Pharma@2026', name: 'Arjun Mehta', role: 'Clinical pharmacist', key: 'pharmacist',
    focus: 'Confirms names the system would not guess and answers deferred alerts', home: '/app/ward' },
  { email: 'prescriber@medsafe.demo', password: 'Medsafe@2026', name: 'Dr. Kavya Iyer', role: 'Consultant physician', key: 'prescriber',
    focus: 'Decides on each alert: accept, override with a reason, or defer', home: '/app/ward' },
  { email: 'reviewer@medsafe.demo', password: 'Review@2026', name: 'Evaluation panel', role: 'Reviewer', key: 'reviewer',
    focus: 'Reads the method, the evidence and the evaluation', home: '/app/why' },
];

/** localStorage can be missing or throw (private windows, blocked storage); every access goes through here. */
export const store = {
  get(key: string) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* storage unavailable */ } },
  remove(key: string) { try { localStorage.removeItem(key); } catch { /* storage unavailable */ } },
};

const SESSION_KEY = 'medsafe.session';

type Auth = {
  user: DemoUser | null;
  signIn: (email: string, password: string) => DemoUser | null;
  signOut: () => void;
};

const AuthContext = createContext<Auth | null>(null);

const find = (email: string | null) => DEMO_USERS.find((u) => u.email === email?.trim().toLowerCase()) ?? null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DemoUser | null>(() => find(store.get(SESSION_KEY)));

  const signIn = (email: string, password: string) => {
    const match = find(email);
    if (!match || match.password !== password) return null;
    store.set(SESSION_KEY, match.email);
    setUser(match);
    return match;
  };

  const signOut = () => {
    store.remove(SESSION_KEY);
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}
