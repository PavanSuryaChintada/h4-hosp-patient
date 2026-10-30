import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { DEMO_USERS, useAuth, type DemoUser, type RoleKey } from '../auth';
import type { WardRow } from '../data/contract';
import { PIN_LABEL, plural } from '../data/format';
import { useData } from '../data/load';
import { DEMO_COMMAND, useMyTasks, useWard } from '../data/ward';
import { ROLE, RoleTile } from './Roles';
import { useToast } from './Toast';
import { Icon } from './viz';

const WARD_NAV = [
  { to: '/app/ward', label: 'Ward patients', nurse: false, tasks: true },
  { to: '/app/ward/new', label: 'Admit a patient', nurse: true, tasks: false },
  { to: '/app/ward/patterns', label: 'Override patterns', nurse: false, tasks: false },
];
const NAV = [
  { to: '/app', label: 'Patient queue' },
  { to: '/app/why', label: 'Why it matters' },
  { to: '/app/intake', label: 'Intake' },
  { to: '/app/resolution', label: 'Name resolution' },
  { to: '/results', label: 'Results' },
  { to: '/architecture', label: 'Architecture' },
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

function useOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) close(); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open, close]);
  return ref;
}

const tasksFor = (rows: WardRow[] | null, role: RoleKey) => (rows ?? []).reduce((n, r) => n + r.tasks.filter((t) => t.role === role).length, 0);

/** Signing in as another demo account, without the sign-in page. Stays on the record being worked on. */
export function useSwitchRole() {
  const { signIn } = useAuth();
  const { rows } = useWard();
  const toast = useToast();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  return (u: DemoUser) => {
    if (!signIn(u.email, u.password)) return;
    const mine = (rows ?? []).flatMap((r) => r.tasks.filter((t) => t.role === u.key).map((t) => ({ ...t, record: r.id })));
    toast({
      tone: 'turn', title: `Signed in as ${u.name}, ${u.role}`,
      body: u.key === 'reviewer' ? 'Read-only: no entries and no decisions.' : mine.length ? `${plural(mine.length, 'task')} waiting for you. ${mine[0].record}: ${mine[0].text}.` : 'Nothing is waiting for you on the ward right now.',
      link: mine.length && !pathname.endsWith(mine[0].record) ? { to: `/app/ward/${mine[0].record}`, label: `Open ${mine[0].record}` } : undefined,
    });
    if (pathname === '/app/ward/new' && u.key !== 'nurse') navigate('/app/ward');
  };
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
        <Link to="/app">Training patients</Link>
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

function WardStatus() {
  const { up } = useWard();
  const label = up === null ? 'Ward: checking' : up ? 'Ward server connected' : 'Ward server not running';
  return <span className={`ward-status status-line tone-${up ? 'done' : 'fail'}`} title={up === false ? `Start it with ${DEMO_COMMAND}` : undefined}><span className="sq" aria-hidden="true" />{label}</span>;
}

function Bell() {
  const { user } = useAuth();
  const { rows, up } = useWard();
  const tasks = useMyTasks();
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  if (!user || !up) return null;
  const others = (['nurse', 'lab', 'pharmacist', 'prescriber'] as RoleKey[]).filter((r) => r !== user.key);
  return (
    <div className="menu-wrap" ref={ref}>
      <button type="button" className={`bell${tasks.length ? ' has' : ''}`} aria-label={`${plural(tasks.length, 'task')} for you`} aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="bell" size={16} />{tasks.length > 0 && <span className="bell-n mono">{tasks.length}</span>}
      </button>
      {open && (
        <div className="menu menu-tasks" role="menu">
          <p className="menu-h">Your tasks, {ROLE[user.key].title.toLowerCase()}</p>
          {tasks.length === 0 && <p className="menu-empty">Nothing is waiting for you.</p>}
          {tasks.map((t) => (
            <Link key={t.record + t.kind} role="menuitem" to={`/app/ward/${t.record}`} className="menu-task status-line tone-turn" onClick={() => setOpen(false)}>
              <span className="sq" aria-hidden="true" /><span className="mono">{t.record}</span><span>{t.text}</span>
            </Link>
          ))}
          <p className="menu-h">Waiting on others</p>
          {others.map((r) => (
            <div key={r} className="menu-other"><RoleTile role={r} size={20} /><span>{ROLE[r].title}</span><span className="mono">{tasksFor(rows, r)}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

function RoleSwitch() {
  const { user } = useAuth();
  const { rows } = useWard();
  const switchTo = useSwitchRole();
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  if (!user) return null;
  return (
    <div className="menu-wrap" ref={ref}>
      <button type="button" className="who" aria-expanded={open} onClick={() => setOpen(!open)}>
        <RoleTile role={user.key} size={24} />
        <span className="who-text"><strong>{user.name}</strong><span>{user.role}</span></span>
        <Icon name="swap" size={14} />
      </button>
      {open && (
        <div className="menu menu-roles" role="menu">
          <p className="menu-h">Switch role (demo accounts)</p>
          {DEMO_USERS.filter((u) => u.email !== user.email).map((u) => {
            const n = u.key === 'reviewer' ? 0 : tasksFor(rows, u.key);
            return (
              <button key={u.email} type="button" role="menuitem" className="menu-role" onClick={() => { setOpen(false); switchTo(u); }}>
                <RoleTile role={u.key} size={28} />
                <span className="menu-role-text"><strong>{u.name}</strong><span>{u.role}</span></span>
                {n > 0 && <span className="task-n mono" title={`${plural(n, 'task')} waiting`}>{n}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

type Step = { role: RoleKey; title: string; text: string; to?: string; done: (r: WardRow | undefined) => boolean };
const STEPS: Step[] = [
  { role: 'nurse', title: 'Admit a patient', text: 'Fetch records through ABHA with the patient\'s consent, or start from a training-set patient. The pipeline checks the list the moment it is saved.', to: '/app/ward/new', done: (r) => !!r },
  { role: 'lab', title: 'Enter eGFR', text: 'The kidney-dose rules re-run on the value. Try 28, then 80, and watch the alerts change.', done: (r) => !!r && r.egfr !== null },
  { role: 'pharmacist', title: 'Confirm names', text: 'Lines the system would not guess wait here. With none, this step is already done.', done: (r) => !!r && !r.tasks.some((t) => t.kind === 'confirm_name') },
  { role: 'prescriber', title: 'Decide on each alert', text: 'Accept, override with a reason, or defer one to the pharmacist.', done: (r) => !!r && r.decisions.submitted > 0 && r.decisions.undecided === 0 },
  { role: 'pharmacist', title: 'Answer what was handed over', text: 'Deferred alerts and review requests land on the pharmacist\'s task list.', done: (r) => !!r && r.decisions.submitted > 0 && r.decisions.undecided === 0 && r.decisions.handed === 0 && !r.review_requested },
];

const LEGEND: [string, string][] = [
  ['turn', 'Your turn, or something you can act on'],
  ['wait', 'Waiting on someone else, or overridden'],
  ['handed', 'With the pharmacist'],
  ['done', 'Done, accepted, or no issue found'],
  ['danger', 'A serious alert in the data'],
];

function Guide({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const { up, rows } = useWard();
  const switchTo = useSwitchRole();
  const latest = rows?.[0];
  const next = STEPS.findIndex((s) => !s.done(latest));
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    document.body.classList.add('drawer-open');
    return () => { document.removeEventListener('keydown', onKey); document.body.classList.remove('drawer-open'); };
  }, [onClose]);
  return (
    <aside className="drawer" aria-label="Demo guide">
      <header className="drawer-head">
        <div><p className="modal-kicker">Demo guide</p><h2 className="section">Run one patient round the ward</h2></div>
        <button type="button" className="modal-x" aria-label="Close the guide" onClick={onClose}><Icon name="x" size={16} /></button>
      </header>
      {up === false ? (
        <div className="drawer-body">
          <p className="guide-off status-line tone-fail"><span className="sq" aria-hidden="true" /><strong>The ward server is not running here.</strong></p>
          <p className="meta">The ward runs the real Python pipeline on every patient you type in, so it needs its local server. On the demo laptop, double-click <span className="mono">{DEMO_COMMAND}</span> in the repo (or run <span className="mono">python tools/serve_ui.py --fresh --open</span>).</p>
          <p className="menu-h" style={{ marginTop: 24 }}>Without the server: the training-set walkthrough</p>
          <ol className="guide-steps">
            {[['Patient queue', 'Every patient, most urgent first', '/app?demo=1'], ['One patient, two checks', 'Flip the switch from the standard EHR check to Medsafe', '/app/why'],
              ['Decide on an alert', 'Accept, override or defer: kept in this browser', '/app?demo=1'], ['The list as written', 'Matches and the lines it would not guess', '/app/resolution'], ['Results', 'The organisers\' scorer, misses included', '/results']]
              .map(([t, s, to], i) => <li key={t} className="guide-step"><span className="guide-n mono">{i + 1}</span><div><strong>{t}</strong><p className="meta">{s}</p><Link to={to} onClick={onClose}>Go →</Link></div></li>)}
          </ol>
        </div>
      ) : (
        <div className="drawer-body">
          <p className="meta">{latest ? <>Following the newest record, <Link to={`/app/ward/${latest.id}`} onClick={onClose} className="mono">{latest.id}</Link>. Steps tick themselves as each role does its part.</> : 'Start as the ward nurse. Steps tick themselves as each role does its part.'}</p>
          <ol className="guide-steps">
            {STEPS.map((s, i) => {
              const done = s.done(latest);
              const now = i === next;
              return (
                <li key={s.title} className={`guide-step${done ? ' done' : now ? ' now' : ''}`}>
                  <span className="guide-n mono">{done ? <Icon name="check" size={14} /> : i + 1}</span>
                  <div>
                    <p className="guide-role"><RoleTile role={s.role} size={20} />{ROLE[s.role].title}</p>
                    <strong>{s.title}</strong>
                    <p className="meta">{s.text}</p>
                    {now && (
                      <div className="guide-actions">
                        {user?.key !== s.role && <button type="button" className="btn btn-turn btn-sm" onClick={() => switchTo(DEMO_USERS.find((u) => u.key === s.role)!)}>Sign in as {ROLE[s.role].title.toLowerCase()}</button>}
                        {s.to ? <Link className="btn btn-secondary btn-sm" to={s.to} onClick={onClose}>Go</Link>
                          : latest && <Link className="btn btn-secondary btn-sm" to={`/app/ward/${latest.id}`} onClick={onClose}>Open {latest.id}</Link>}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
            <li className={`guide-step${next === -1 ? ' now' : ''}`}>
              <span className="guide-n mono">{STEPS.length + 1}</span>
              <div><strong>See the override patterns</strong><p className="meta">Which alerts the ward overrides most, and why, from the audit log.</p><Link to="/app/ward/patterns" onClick={onClose}>Open override patterns →</Link></div>
            </li>
          </ol>
        </div>
      )}
      <div className="drawer-foot">
        <p className="menu-h">What the colours mean</p>
        <ul className="legend-list">
          {LEGEND.map(([tone, text]) => <li key={tone} className={`status-line tone-${tone}`}><span className="sq" aria-hidden="true" />{text}</li>)}
        </ul>
      </div>
    </aside>
  );
}

/** New tasks for the signed-in role pop up as they arrive from other roles. */
function useTaskAlerts() {
  const { user } = useAuth();
  const { rows } = useWard();
  const tasks = useMyTasks();
  const toast = useToast();
  const seen = useRef<{ who: string | undefined; keys: Set<string> } | null>(null);
  useEffect(() => {
    if (rows === null) return;
    const keys = new Set(tasks.map((t) => `${t.record}:${t.kind}`));
    if (seen.current === null || seen.current.who !== user?.key) { seen.current = { who: user?.key, keys }; return; }
    for (const t of tasks) {
      if (!seen.current.keys.has(`${t.record}:${t.kind}`)) {
        toast({ tone: 'turn', title: `New for you: ${t.record}`, body: t.text, link: { to: `/app/ward/${t.record}`, label: `Open ${t.record}` } });
      }
    }
    seen.current = { who: user?.key, keys };
  }, [rows, tasks, user, toast]);
}

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { user, signOut } = useAuth();
  const { x } = useData();
  const demo = useDemo();
  const mine = useMyTasks();
  const [guide, setGuide] = useState(false);
  useTaskAlerts();

  return (
    <>
      <aside className="rail">
        <div className="rail-brand">
          <Link to="/" className="name"><span className="brand-mark" aria-hidden="true" />Medsafe</Link>
          <div className="sub">Medication safety, a second pair of eyes</div>
        </div>
        {user && (
          <div className="rail-me">
            <RoleTile role={user.key} size={36} />
            <div>
              <div className="rail-user-name">{user.name}</div>
              <div className="meta">{user.role}</div>
            </div>
            <p className="rail-does">{ROLE[user.key].does}</p>
          </div>
        )}
        <nav aria-label="Ward">
          <span className="rail-group">Ward, live</span>
          {WARD_NAV.filter((n) => !n.nurse || user?.key === 'nurse').map((n) => (
            <NavLink key={n.to} to={n.to} end
              className={({ isActive }) => (isActive || (n.to === '/app/ward' && /^\/app\/ward\/WARD-/.test(pathname)) ? 'active' : '')}>
              {n.label}{n.tasks && mine.length > 0 && <span className="nav-n mono" title={`${plural(mine.length, 'task')} for you`}>{mine.length}</span>}
            </NavLink>
          ))}
        </nav>
        <nav aria-label="Training data">
          <span className="rail-group">Training data, from the pipeline</span>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/app'}
              className={({ isActive }) => (isActive || (n.to === '/app' && pathname.startsWith('/app/patient')) ? 'active' : '')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          {user && <button type="button" className="btn-link" onClick={signOut}>Sign out</button>}
          <p style={{ marginTop: 8 }}>Pipeline output, {x.source.split} split, <span className="mono">{x.source.patients}</span> patients</p>
        </div>
      </aside>
      <header className="topbar">
        <Crumbs />
        <div className="chips">
          <WardStatus />
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setGuide(!guide)} aria-expanded={guide}><Icon name="guide" size={16} />Demo guide</button>
          <Bell />
          <RoleSwitch />
          <span className="chip">Prototype · simulated dataset</span>
        </div>
      </header>
      <main className="main">
        {demo && <PinBar />}
        {children}
      </main>
      {guide && <Guide onClose={() => setGuide(false)} />}
    </>
  );
}
