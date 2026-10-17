import type { ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../auth';
import { INTERACTIONS } from '../data/drugs';
import { useTour } from './Tour';

const NAV = [
  { to: '/app', label: 'Patients' },
  { to: '/app/resolution', label: 'Name resolution' },
  { to: '/app/method', label: 'Method' },
  { to: '/app/evaluation', label: 'Evaluation' },
];

function Crumbs() {
  const { pathname } = useLocation();
  const patient = pathname.match(/^\/app\/patient\/(\w+)/);
  if (patient) {
    return (
      <div className="crumbs">
        <Link to="/app">Patients</Link>
        <span className="sep" aria-hidden="true">›</span>
        <span className="here mono">{patient[1]}</span>
      </div>
    );
  }
  const here = NAV.find((n) => n.to === pathname)?.label ?? 'Patients';
  return <div className="crumbs"><span className="here">{here}</span></div>;
}

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { user, signOut } = useAuth();
  const { start, active } = useTour();

  return (
    <>
      <aside className="rail">
        <div className="rail-brand">
          <Link to="/" className="name">Medsafe</Link>
          <div className="sub">Medication safety, a second pair of eyes</div>
        </div>
        <nav aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/app'}
              className={({ isActive }) => (isActive || (n.to === '/app' && pathname.startsWith('/app/patient')) ? 'active' : '')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          {user && (
            <div className="rail-user">
              <div className="rail-user-name">{user.name}</div>
              <div>{user.role}</div>
              <button type="button" className="btn-link" onClick={signOut}>Sign out</button>
            </div>
          )}
          General medicine, ward 4B<br />
          Rule tables: <span className="mono">{INTERACTIONS.length}</span> interaction rules
        </div>
      </aside>
      <header className="topbar">
        <Crumbs />
        <div className="chips">
          <button type="button" className="btn btn-secondary btn-sm" onClick={start} disabled={active}>Take the walkthrough</button>
          <span className="chip">Prototype · simulated dataset</span>
        </div>
      </header>
      <main className="main">{children}</main>
    </>
  );
}
