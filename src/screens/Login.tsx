import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { DEMO_USERS, store, TOUR_PENDING_KEY, TOUR_SEEN_KEY, useAuth, type DemoUser } from '../auth';
import { METRICS } from '../data/engine';
import { NEAR_MISS } from '../data/evaluation';

export function Login() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [failed, setFailed] = useState(false);
  const [tour, setTour] = useState(params.get('tour') === '1' || store.get(TOUR_SEEN_KEY) !== '1');

  const from = (location.state as { from?: string } | null)?.from ?? '/app';
  if (user) return <Navigate to={from} replace />;

  const enter = (u: DemoUser | null) => {
    if (!u) { setFailed(true); return; }
    if (tour) store.set(TOUR_PENDING_KEY, '1');
    navigate(from, { replace: true });
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
        <Link to="/" className="lp-brand">Medsafe</Link>

        <div className="login-form-wrap">
          <h1 className="display">Sign in</h1>
          <p className="meta" style={{ marginTop: 4 }}>This is a demo build. Use one of the accounts below.</p>

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
            <label className="check">
              <input type="checkbox" checked={tour} onChange={(e) => setTour(e.target.checked)} />
              Start the guided walkthrough after signing in
            </label>
            <button type="submit" className="btn btn-primary btn-block">Sign in</button>
          </form>

          <section className="creds" aria-labelledby="creds-title">
            <h2 id="creds-title" className="label">Demo accounts. Click one to sign in.</h2>
            {DEMO_USERS.map((u) => (
              <button key={u.email} type="button" className="cred" onClick={() => signInAs(u)} aria-label={`Sign in as ${u.name}, ${u.role}`}>
                <span className="cred-head">
                  <span className="cred-name">{u.name}</span>
                  <span className="cred-role">{u.role}</span>
                </span>
                <span className="cred-focus">{u.focus}</span>
                <span className="cred-keys">
                  <span><span className="k">Email</span><span className="mono">{u.email}</span></span>
                  <span><span className="k">Password</span><span className="mono">{u.password}</span></span>
                </span>
              </button>
            ))}
          </section>
        </div>

        <p className="login-foot">Prototype on a simulated dataset. No real patient data. <Link to="/">Back to the overview</Link></p>
      </main>

      <aside className="login-side" aria-label="What you will see">
        <div className="login-side-inner">
          <h2 className="lp-h3">What you will see</h2>
          <ol className="login-list">
            <li><strong>A queue of 40 prescriptions</strong> ranked by how urgently each needs a change.</li>
            <li><strong>Patient 2291</strong>, whose eleven raw warnings collapse into three alerts and one clear action.</li>
            <li><strong>The slip as written</strong> next to what each line resolved to, including the one it would not guess.</li>
            <li><strong>The evaluation</strong>: alert volume and near-miss recall reported side by side, misses included.</li>
          </ol>
          <dl className="login-figs">
            <div><dt>Alerts per patient</dt><dd className="mono">{METRICS.alertsBefore.toFixed(1)} to {METRICS.alertsAfter.toFixed(1)}</dd></div>
            <div><dt>Near-miss recall</dt><dd className="mono">{NEAR_MISS.caught} / {NEAR_MISS.seeded}</dd></div>
          </dl>
        </div>
      </aside>
    </div>
  );
}
