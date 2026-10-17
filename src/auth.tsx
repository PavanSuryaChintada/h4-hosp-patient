// Hardcoded demo accounts. There is no backend: the session is a key in localStorage.

import { createContext, useContext, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

export type DemoUser = { email: string; password: string; name: string; role: string; focus: string };

export const DEMO_USERS: DemoUser[] = [
  { email: 'prescriber@medsafe.demo', password: 'Medsafe@2026', name: 'Dr. Kavya Iyer', role: 'Consultant physician', focus: 'Checks prescriptions before they leave the ward' },
  { email: 'pharmacist@medsafe.demo', password: 'Pharma@2026', name: 'Arjun Mehta', role: 'Clinical pharmacist', focus: 'Audits name matches and duplicate therapy' },
  { email: 'reviewer@medsafe.demo', password: 'Review@2026', name: 'Evaluation panel', role: 'Reviewer', focus: 'Reads the method and the evaluation' },
];

/** localStorage can be missing or throw (private windows, blocked storage); every access goes through here. */
export const store = {
  get(key: string) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* storage unavailable */ } },
  remove(key: string) { try { localStorage.removeItem(key); } catch { /* storage unavailable */ } },
};

const SESSION_KEY = 'medsafe.session';
export const TOUR_PENDING_KEY = 'medsafe.tour.pending';
export const TOUR_SEEN_KEY = 'medsafe.tour.seen';

type Auth = {
  user: DemoUser | null;
  /** True right after an explicit sign-out, so protected pages send people to the overview, not the sign-in form. */
  signedOut: boolean;
  signIn: (email: string, password: string) => DemoUser | null;
  signOut: () => void;
};

const AuthContext = createContext<Auth | null>(null);

const find = (email: string | null) => DEMO_USERS.find((u) => u.email === email?.trim().toLowerCase()) ?? null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DemoUser | null>(() => find(store.get(SESSION_KEY)));
  const [signedOut, setSignedOut] = useState(false);

  const signIn = (email: string, password: string) => {
    const match = find(email);
    if (!match || match.password !== password) return null;
    store.set(SESSION_KEY, match.email);
    setSignedOut(false);
    setUser(match);
    return match;
  };

  const signOut = () => {
    store.remove(SESSION_KEY);
    setSignedOut(true);
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, signedOut, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, signedOut } = useAuth();
  const location = useLocation();
  if (!user && signedOut) return <Navigate to="/" replace />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}
