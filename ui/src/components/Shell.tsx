import { useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth';
import { PIN_LABEL } from '../data/format';
import { useData } from '../data/load';

const WARD_NAV = [
  { to: '/app/ward', label: 'Ward patients', nurse: false },
  { to: '/app/ward/new', label: 'Admit a patient', nurse: true },
  { to: '/app/ward/patterns', label: 'Override patterns', nurse: false },
];
const NAV = [
  { to: '/app', label: 'Patient queue' },
  { to: '/app/why', label: 'Why it matters' },
  { to: '/app/intake', label: 'Intake' },
  { to: '/app/resolution', label: 'Name resolution' },
  { to: '/app/evaluation', label: 'Evaluation' },
];

const DEMO_KEY = 'medsafe.demo';

/** `?demo=1` turns the pinned demo patients on for the session; `?demo=0` turns them off. */
export function useDemo(): boolean {
  const [params] = useSearchParams();
  const flag = params.get('demo');
  const [on, setOn] = useState(() => {
    try { return flag === '1' || (flag !== '0' && sessionStorage.getItem(DEMO_KEY) === '1'); } catch { return flag === '1'; }
  });
  useEffect(() => {
    if (flag !== '1' && flag !== '0') return;
    try { flag === '1' ? sessionStorage.setItem(DEMO_KEY, '1') : sessionStorage.removeItem(DEMO_KEY); } catch { /* storage unavailable */ }
    setOn(flag === '1');
  }, [flag]);
  return on;
}

function Crumbs() {
  const { pathname } = useLocation();
  const record = pathname.match(/^\/app\/ward\/(WARD-\d+)/);
  if (record) {
    return (
      <div className="crumbs">
        <Link to="/app/ward">Ward</Link>
        <span className="sep" aria-hidden="true">›</span>
        <span className="here mono">{record[1]}</span>
      </div>
    );
  }
  const patient = pathname.match(/^\/app\/patient\/([\w-]+)/);
  if (patient) {
    return (
      <div className="crumbs">
        <Link to="/app">Patients</Link>
        <span className="sep" aria-hidden="true">›</span>
        <span className="here mono">{patient[1]}</span>
      </div>
    );
  }
  const here = [...WARD_NAV, ...NAV].find((n) => n.to === pathname)?.label ?? 'Patients';
  return <div className="crumbs"><span className="here">{here}</span></div>;
}

function PinBar() {
  const { x } = useData();
  const { pathname } = useLocation();
  if (!x.demo) return null;
  return (
    <nav className="pinbar" aria-label="Demo patients">
      <span className="pinbar-k">Demo patients</span>
      {x.demo.pins.filter((p) => p.patient_ids.length).map((p) => (
        <span key={p.slot} className="pinbar-item">
          <span className="pinbar-l">{PIN_LABEL[p.slot]}</span>
          {p.patient_ids.map((id) => (
            <Link key={id} to={`/app/patient/${id}`} className="mono" aria-current={pathname.endsWith(id) ? 'page' : undefined}>{id}</Link>
          ))}
        </span>
      ))}
    </nav>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { user, signOut } = useAuth();
  const { x } = useData();
  const demo = useDemo();
  const built = x.stages.filter((s) => s.built).map((s) => s.id);

  return (
    <>
      <aside className="rail">
        <div className="rail-brand">
          <Link to="/app" className="name"><span className="brand-mark" aria-hidden="true" />Medsafe</Link>
          <div className="sub">Medication safety, a second pair of eyes</div>
        </div>
        <nav aria-label="Ward">
          <span className="rail-group">Ward</span>
          {WARD_NAV.filter((n) => !n.nurse || user?.key === 'nurse').map((n) => (
            <NavLink key={n.to} to={n.to} end
              className={({ isActive }) => (isActive || (n.to === '/app/ward' && /^\/app\/ward\/WARD-/.test(pathname)) ? 'active' : '')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <nav aria-label="Training data">
          <span className="rail-group">Training data</span>
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
          Pipeline output, {x.source.split} split<br />
          <span className="mono">{x.source.patients}</span> patients · stages built: <span className="mono">{built.join(', ')}</span>
        </div>
      </aside>
      <header className="topbar">
        <Crumbs />
        <div className="chips"><span className="chip">Prototype · simulated dataset</span></div>
      </header>
      <main className="main">
        {demo && <PinBar />}
        {children}
      </main>
    </>
  );
}
