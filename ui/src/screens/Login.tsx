import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { DEMO_USERS, useAuth, type DemoUser } from '../auth';

export function Login() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [failed, setFailed] = useState(false);

  const from = (location.state as { from?: string } | null)?.from;
  if (user) return <Navigate to={from ?? user.home} replace />;

  const enter = (u: DemoUser | null) => {
    if (!u) { setFailed(true); return; }
    navigate(from ?? u.home, { replace: true });
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

        <p className="login-foot">Prototype on the synthetic H4 dataset. No real patient data.</p>
      </main>

      <aside className="login-side" aria-label="What you will see">
        <div className="login-side-inner">
          <h2 className="lp-h3">What you will see</h2>
          <ol className="login-list">
            <li><strong>A ward, end to end.</strong> A nurse admits a patient, the lab adds eGFR, the pharmacist confirms names, the prescriber decides on each alert.</li>
            <li><strong>One patient, two checks.</strong> A switch flips the same list between a standard EHR check and Medsafe.</li>
            <li><strong>Four ways a standard check fails</strong>, each on a real patient from the training set.</li>
            <li><strong>The list as written</strong> next to what each line resolved to, including the ones it would not guess.</li>
            <li><strong>The evaluation</strong> from the organisers' scorer, misses included.</li>
          </ol>
          <p className="login-note">Every check runs the real pipeline in Python, on the pack's data or on the patient you enter. The browser computes nothing.</p>
        </div>
      </aside>
    </div>
  );
}
