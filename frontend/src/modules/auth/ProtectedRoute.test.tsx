import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import { fetchCurrentUser } from './api';
import { AuthProvider } from './AuthContext';
import { ProtectedRoute } from './ProtectedRoute';
import type { User } from './types';

vi.mock('./api');

const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);

const member: User = {
  id: 'u1',
  organisation_id: 'o1',
  email: 'member@example.com',
  full_name: 'A Member',
  role: 'member',
  is_active: true,
};

const admin: User = { ...member, id: 'u2', email: 'admin@example.com', role: 'admin' };

function renderProtected(requireAdmin: boolean): void {
  render(
    <MemoryRouter initialEntries={['/protected']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>Login page</p>} />
          <Route path="/" element={<p>Dashboard</p>} />
          <Route element={<ProtectedRoute requireAdmin={requireAdmin} />}>
            <Route path="/protected" element={<p>Protected content</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  afterEach(() => {
    vi.resetAllMocks();
    clearToken();
  });

  it('redirects to /login when unauthenticated', async () => {
    renderProtected(false);

    await waitFor(() => {
      expect(screen.getByText('Login page')).toBeInTheDocument();
    });
  });

  it('renders the nested route once authenticated', async () => {
    setToken('a.jwt.token');
    mockedFetchCurrentUser.mockResolvedValue(member);

    renderProtected(false);

    await waitFor(() => {
      expect(screen.getByText('Protected content')).toBeInTheDocument();
    });
  });

  it('redirects a non-admin away from an admin-only route', async () => {
    setToken('a.jwt.token');
    mockedFetchCurrentUser.mockResolvedValue(member);

    renderProtected(true);

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });
  });

  it('renders an admin-only route for an admin', async () => {
    setToken('a.jwt.token');
    mockedFetchCurrentUser.mockResolvedValue(admin);

    renderProtected(true);

    await waitFor(() => {
      expect(screen.getByText('Protected content')).toBeInTheDocument();
    });
  });
});
