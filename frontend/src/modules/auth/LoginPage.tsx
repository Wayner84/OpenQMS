import { useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { ApiError } from '../../shared/api/client';
import { useAuth } from './AuthContext';

/** The login screen. Redirects to `/` (or the page the user was sent from) on success. */
export function LoginPage(): ReactElement {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authenticated') {
    const state = location.state as { from?: { pathname: string } } | null;
    return <Navigate to={state?.from?.pathname ?? '/'} replace />;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    void (async () => {
      try {
        await login(email, password);
        await navigate('/', { replace: true });
      } catch (err) {
        setError(
          err instanceof ApiError && err.status === 401
            ? 'Incorrect email or password.'
            : 'Something went wrong. Please try again.',
        );
      } finally {
        setSubmitting(false);
      }
    })();
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} aria-label="Log in">
      <h1>Log in</h1>
      {error && (
        <p role="alert" className="auth-form__error">
          {error}
        </p>
      )}
      <div className="form-field">
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
          }}
        />
      </div>
      <div className="form-field">
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
        />
      </div>
      <button type="submit" disabled={submitting}>
        {submitting ? 'Logging in…' : 'Log in'}
      </button>
    </form>
  );
}
