import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { DEMO_USERS, useAuth, type DemoUser } from '../auth';
import { CARE_PATH, ROLE, RoleTile } from '../components/Roles';
import { useToast } from '../components/Toast';
import { DEMO_COMMAND, useWard } from '../data/ward';

export function Login() {
  const { user, signIn } = useAuth();
  const { up } = useWard();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [failed, setFailed] = useState(false);

  const from = (location.state as { from?: string } | null)?.from;
  // Without the ward server (the hosted site), the ward pages cannot work: start on the training set.
  const home = (u: DemoUser) => (up === false && u.home.startsWith('/app/ward') ? '/app?demo=1' : u.home);
  if (user) return <Navigate to={from ?? home(user)} replace />;

  const enter = (u: DemoUser | null) => {
    if (!u) { setFailed(true); return; }
    toast({ tone: 'turn', title: `Welcome, ${u.name}`, body: `${u.role}. ${ROLE[u.key].does}.` });
    navigate(from ?? home(u), { replace: true });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    enter(signIn(email, password));
  };

  const signInAs = (u: DemoUser) => {
    setEmail(u.email);
    setPassword(u.password);
    enter(signIn(u.email, u.password));
  };

  return (
    <div className="login">
      <main className="login-main">
        <span className="lp-brand"><span className="brand-mark" aria-hidden="true" />Medsafe</span>

        <div className="login-form-wrap">
          <h1 className="display">Sign in</h1>
          <p className="meta" style={{ marginTop: 4 }}>This is a demo build. Pick an account below; you can switch role from the top bar at any time.</p>

          <form className="login-form" onSubmit={onSubmit} noValidate>
            <label className="field">
              <span className="label">Email</span>
              <input type="email" autoComplete="username" value={email} onChange={(e) => { setEmail(e.target.value); setFailed(false); }} />
            </label>
            <label className="field">
              <span className="label">Password</span>
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => { setPassword(e.target.value); setFailed(false); }} />
            </label>
            {failed && (
              <p className="form-error" role="alert">
                That email and password do not match a demo account. Pick an account below to fill both in.
              </p>
            )}
            <button type="submit" className="btn btn-primary btn-block">Sign in</button>
          </form>

          <section className="creds" aria-labelledby="creds-title">
            <h2 id="creds-title" className="label">Demo accounts, in the order a patient meets them. Click one to sign in.</h2>
            {DEMO_USERS.map((u) => {
              const step = CARE_PATH.indexOf(u.key);
              return (
                <button key={u.email} type="button" className={`cred${step === 0 ? ' cred-first' : ''}`} onClick={() => signInAs(u)} aria-label={`Sign in as ${u.name}, ${u.role}`}>
                  <span className="cred-step mono">{step >= 0 ? step + 1 : '·'}</span>
                  <RoleTile role={u.key} size={36} />
                  <span className="cred-body">
                    <span className="cred-head">
                      <span className="cred-name">{u.name}</span>
                      <span className="cred-role">{u.role}{step === 0 ? ' · start here' : ''}</span>
                    </span>
                    <span className="cred-focus">{u.focus}</span>
                    <span className="cred-keys">
                      <span><span className="k">Email</span><span className="mono">{u.email}</span></span>
                      <span><span className="k">Password</span><span className="mono">{u.password}</span></span>
                    </span>
                  </span>
                </button>
              );
            })}
          </section>
        </div>

        <p className="login-foot">Prototype on the synthetic H4 dataset. No real patient data. <Link to="/">About Medsafe</Link></p>
      </main>

      <aside className="login-side" aria-label="How the demo runs">
        <div className="login-side-inner">
          <h2 className="lp-h3">One patient, round the ward</h2>
          <ol className="flow">
            {CARE_PATH.map((r, i) => (
              <li key={r} className="flow-step">
                <span className="flow-n mono">{i + 1}</span>
                <RoleTile role={r} size={32} />
                <span><strong>{ROLE[r].title}</strong><span className="meta">{ROLE[r].does}</span></span>
              </li>
            ))}
          </ol>
          <p className={`login-ward status-line tone-${up ? 'done' : 'fail'}`}>
            <span className="sq" aria-hidden="true" />
            {up === null ? 'Checking for the ward server' : up
              ? <span><strong>Ward server connected.</strong> Every patient you enter is checked by the real pipeline, and every role sees the others' work.</span>
              : <span><strong>Ward server not running here.</strong> The training-set demo works as it is. For the live ward, run <span className="mono">{DEMO_COMMAND}</span> on the demo laptop.</span>}
          </p>
          <p className="login-note">Colour means the state of the work: blue is your turn, amber is waiting on someone, purple is with the pharmacist, green is done. Red is kept for danger in the data.</p>
        </div>
      </aside>
    </div>
  );
}
