import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';

import { onUnauthorized } from '../../shared/auth/sessionEvents';
import { clearToken, getToken, setToken } from '../../shared/auth/tokenStore';
import { fetchCurrentUser, login as loginRequest, logout as logoutRequest } from './api';
import type { User } from './types';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Resolves the current session from a stored token on mount (re-validating it
 * against `GET /me`, since a stored token may have expired or been revoked since
 * the last visit), and exposes `login`/`logout` to the rest of the app.
 */
export function AuthProvider({ children }: { children: ReactNode }): ReactElement {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // An object property, not a plain `let`, so TypeScript doesn't narrow
    // `cancelled.current` to a literal `false` across the closure boundary below
    // (it's reassigned from the effect cleanup, a separate function).
    const cancelled = { current: false };

    void (async () => {
      const token = getToken();
      if (!token) {
        if (!cancelled.current) {
          setStatus('unauthenticated');
        }
        return;
      }
      try {
        const currentUser = await fetchCurrentUser();
        if (!cancelled.current) {
          setUser(currentUser);
          setStatus('authenticated');
        }
      } catch {
        clearToken();
        if (!cancelled.current) {
          setUser(null);
          setStatus('unauthenticated');
        }
      }
    })();

    return () => {
      cancelled.current = true;
    };
  }, []);

  useEffect(
    () =>
      // Any request anywhere in the app can discover the token is no longer valid
      // (expiry, logout-elsewhere revocation, or deactivation) well after the
      // initial mount check above already passed. Reset locally only -- the
      // token is already invalid server-side, so there is no backend call to make.
      onUnauthorized(() => {
        clearToken();
        setUser(null);
        setStatus('unauthenticated');
      }),
    [],
  );

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest({ email, password });
    setToken(response.access_token);
    setUser(response.user);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    // Always clear the local session, even if the backend call fails (e.g. the
    // network is down, or the token was already revoked) -- the user's intent to
    // log out of this browser must not depend on server reachability.
    try {
      await logoutRequest();
    } catch {
      // Swallowed deliberately; see above.
    } finally {
      clearToken();
      setUser(null);
      setStatus('unauthenticated');
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout }),
    [status, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
