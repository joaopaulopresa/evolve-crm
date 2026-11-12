import { type FormEvent, useState } from "react";

import { useAuth } from "../auth";
import { TextField } from "../components/Field";

export function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-pitch">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Evolve CRM
        </div>
        <h1>The CRM that changes when your business does.</h1>
        <p>
          Track companies, contacts and deals. When you need something it does not do yet, describe
          it and review the change before it goes live.
        </p>
      </section>
      <form className="login-form" onSubmit={submit}>
        <h2>Sign in</h2>
        <TextField
          label="E-mail"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
