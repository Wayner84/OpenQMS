import { render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { emitUnauthorized } from '../../shared/auth/sessionEvents';
import { clearToken, getToken, setToken } from '../../shared/auth/tokenStore';
import { fetchCurrentUser, login, logout } from './api';
import { AuthProvider, useAuth } from './AuthContext';
import type { User } from './types';

vi.mock('./api');

const mockedLogin = vi.mocked(login);
const mockedLogout = vi.mocked(logout);
const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);

const user: User = {
  id: 'u1',
  organisation_id: 'o1',
  email: 'ada@example.com',
  full_name: 'Ada Lovelace',
  role: 'member',
  is_active: true,
};

function Probe(): ReactElement {
  const { status, user: currentUser, login: doLogin, logout: doLogout } = useAuth();
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="user">{currentUser?.full_name ?? 'none'}</p>
      <button
        onClick={() => {
          void doLogin('ada@example.com', 'secret');
        }}
      >
        login
      </button>
      <button
        onClick={() => {
          void doLogout();
        }}
      >
        logout
      </button>
    </div>
  );
}

describe('AuthProvider', () => {
  afterEach(() => {
    vi.resetAllMocks();
    clearToken();
  });

  it('resolves to unauthenticated when no token is stored', async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated');
    });
    expect(mockedFetchCurrentUser).not.toHaveBeenCalled();
  });

  it('resolves to authenticated by validating a stored token against GET /me', async () => {
    setToken('stored.token');
    mockedFetchCurrentUser.mockResolvedValue(user);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated');
    });
    expect(screen.getByTestId('user')).toHaveTextContent('Ada Lovelace');
  });

  it('clears an invalid stored token and becomes unauthenticated', async () => {
    setToken('expired.token');
    mockedFetchCurrentUser.mockRejectedValue(new Error('401'));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated');
    });
    expect(getToken()).toBeNull();
  });

  it('login() stores the token and sets the authenticated user', async () => {
    mockedFetchCurrentUser.mockRejectedValue(new Error('no token yet'));
    mockedLogin.mockResolvedValue({ access_token: 'new.token', token_type: 'bearer', user });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated');
    });

    screen.getByText('login').click();

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated');
    });
    expect(getToken()).toBe('new.token');
  });

  it('clears the session when a request elsewhere reports the token is no longer valid', async () => {
    setToken('stored.token');
    mockedFetchCurrentUser.mockResolvedValue(user);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated');
    });

    emitUnauthorized();

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated');
    });
    expect(getToken()).toBeNull();
  });

  it('logout() clears the token even if the backend call fails', async () => {
    setToken('stored.token');
    mockedFetchCurrentUser.mockResolvedValue(user);
    mockedLogout.mockRejectedValue(new Error('network error'));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated');
    });

    screen.getByText('logout').click();

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated');
    });
    expect(getToken()).toBeNull();
  });
});
