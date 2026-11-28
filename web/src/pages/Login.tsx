import React, { useEffect, useRef, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ToolId } from '../data/workspace';
import { apiClient } from '../lib/api-client';
import type { AuthStatus } from '../lib/api-client';
import { BrandShieldIcon, ToolIcon } from '../lib/icons';

const ENGINE_ORDER: ToolId[] = ['ioc', 'malware', 'phishing', 'events', 'ruleforge'];

/* The gate in front of the control plane. Two modes share one form: first run
   asks the analyst to choose the password, every later visit asks for it. It is
   deliberately not a marketing landing page: the left panel states what the
   workspace is and what runs in it, the right panel is the one thing to do. */
export function Login({
  mode,
  onAuthenticated
}: {
  mode: 'setup' | 'login';
  onAuthenticated: (status: AuthStatus) => void;
}) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const isSetup = mode === 'setup';

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setError('');
    if (isSetup && password.length < 12) {
      setError('Choose a password of at least 12 characters.');
      return;
    }
    if (isSetup && password !== confirm) {
      setError('The two entries do not match.');
      return;
    }
    if (!password) {
      setError('Enter your password.');
      return;
    }
    setBusy(true);
    try {
      const status = isSetup ? await apiClient.authSetup(password) : await apiClient.authLogin(password);
      onAuthenticated(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed.');
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <section className="auth-brand" aria-label="About this workspace">
        <div className="auth-brand-head">
          <BrandShieldIcon size={24} />
          <span className="auth-brand-name">Seclyst</span>
        </div>

        <div className="auth-brand-copy">
          <h1 className="auth-brand-title">Five security tools, one local workspace.</h1>
          <p className="ui-body">
            This workbench runs on this machine. Your evidence, credentials and results stay here, behind the
            password you set on the right.
          </p>
        </div>

        <ul className="auth-engines" aria-label="Engines in this workspace">
          {ENGINE_ORDER.map((id) => (
            <li key={id} data-tool={id}>
              <span className="auth-engine-mark">
                <ToolIcon tool={id} size={15} />
              </span>
              <span>{TOOLS_REGISTRY[id].name}</span>
            </li>
          ))}
        </ul>

        <p className="auth-brand-foot ui-meta">Loopback only. Nothing is exposed to your network.</p>
      </section>

      <section className="auth-panel" aria-label={isSetup ? 'Set a password' : 'Sign in'}>
        <form className="auth-form" onSubmit={submit}>
          <div className="auth-form-head">
            <h2 className="ui-h2">{isSetup ? 'Set your password' : 'Sign in'}</h2>
            <p className="ui-meta">
              {isSetup
                ? 'This is the first run. Choose the password that opens this workspace; it is stored only as a salted hash.'
                : 'Enter the password for this workspace.'}
            </p>
          </div>

          <label className="auth-field">
            <span className="ui-label">Password</span>
            <input
              ref={inputRef}
              type="password"
              className="ui-input"
              autoComplete={isSetup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={error ? 'true' : undefined}
            />
          </label>

          {isSetup && (
            <label className="auth-field">
              <span className="ui-label">Confirm password</span>
              <input
                type="password"
                className="ui-input"
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
              />
            </label>
          )}

          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="ui-btn ui-btn--primary" disabled={busy}>
            {busy ? 'Checking…' : isSetup ? 'Set password and continue' : 'Continue'}
          </button>

          <p className="auth-hint ui-meta">
            {isSetup
              ? 'Minimum 12 characters. There is no recovery address: this machine is the recovery.'
              : 'Forgot it? Stop Seclyst, delete data/auth.json, and start again to set a new one.'}
          </p>
        </form>
      </section>
    </div>
  );
}