import type { ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { INTERACTIONS } from '../data/drugs';

const NAV = [
  { to: '/', label: 'Patients' },
  { to: '/resolution', label: 'Name resolution' },
  { to: '/method', label: 'Method' },
  { to: '/evaluation', label: 'Evaluation' },
];

function Crumbs() {
  const { pathname } = useLocation();
  const patient = pathname.match(/^\/patient\/(\w+)/);
  if (patient) {
    return (
      <div className="crumbs">
        <Link to="/">Patients</Link>
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
  return (
    <>
      <aside className="rail">
        <div className="rail-brand">
          <div className="name">Medsafe</div>
          <div className="sub">Medication safety, a second pair of eyes</div>
        </div>
        <nav aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}
              className={({ isActive }) => (isActive || (n.to === '/' && pathname.startsWith('/patient')) ? 'active' : '')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          General medicine, ward 4B<br />
          Rule tables: <span className="mono">{INTERACTIONS.length}</span> interaction rules
        </div>
      </aside>
      <header className="topbar">
        <Crumbs />
        <div className="chips"><span className="chip">Prototype · simulated dataset</span></div>
      </header>
      <main className="main">{children}</main>
    </>
  );
}
