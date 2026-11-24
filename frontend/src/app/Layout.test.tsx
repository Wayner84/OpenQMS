import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchCurrentUser, logout } from '../modules/auth/api';
import { AuthProvider } from '../modules/auth/AuthContext';
import { ProtectedRoute } from '../modules/auth/ProtectedRoute';
import type { User } from '../modules/auth/types';
import { clearToken, setToken } from '../shared/auth/tokenStore';
import { ThemeProvider } from '../shared/theme/ThemeProvider';
import { Layout } from './Layout';

vi.mock('../modules/auth/api');

const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);
const mockedLogout = vi.mocked(logout);

const user: User = {
  id: 'u1',
  organisation_id: 'o1',
  email: 'ada@example.com',
  full_name: 'Ada Lovelace',
  role: 'member',
  is_active: true,
};

const admin: User = { ...user, id: 'u2', role: 'admin' };

describe('Layout', () => {
  beforeEach(() => {
    // jsdom (this project's Vitest test environment) doesn't implement
    // matchMedia; ThemeProvider (rendered here because Layout uses ThemeToggle)
    // needs it to resolve the OS light/dark preference.
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
  });

  afterEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
    clearToken();
  });

  it("shows the authenticated user's name and logs out on click", async () => {
    setToken('a.jwt.token');
    mockedFetchCurrentUser.mockResolvedValue(user);
    mockedLogout.mockResolvedValue(undefined);

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<p>Login page</p>} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<p>Home</p>} />
                </Route>
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </ThemeProvider>,
    );

    const logoutButton = await screen.findByRole('button', { name: /log out.*ada lovelace/i });
    fireEvent.click(logoutButton);

    await waitFor(() => {
      expect(screen.getByText('Login page')).toBeInTheDocument();
    });
    expect(mockedLogout).toHaveBeenCalledOnce();
  });

  it('hides the Users nav link from a non-admin', async () => {
    setToken('a.jwt.token');
    mockedFetchCurrentUser.mockResolvedValue(user);

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <Routes>
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<p>Home</p>} />
                </Route>
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </ThemeProvider>,
    );

    await screen.findByText(/log out/i);
    expect(screen.queryByRole('link', { name: /users/i })).not.toBeInTheDocument();
  });

  it('shows the Companies and People nav links to a non-admin', async () => {
    setToken('a.jwt.token');
    mockedFetchCurrentUser.mockResolvedValue(user);

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <Routes>
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<p>Home</p>} />
                </Route>
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </ThemeProvider>,
    );

    expect(await screen.findByRole('link', { name: /^companies$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^people$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^suppliers$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^products$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^ncr$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^calibration$/i })).toHaveAttribute(
      'href',
      '/calibration/assets',
    );
    expect(screen.getByRole('link', { name: /^due$/i })).toHaveAttribute(
      'href',
      '/calibration/due',
    );
  });

  it('shows the Users nav link to an admin', async () => {
    setToken('a.jwt.token');
    mockedFetchCurrentUser.mockResolvedValue(admin);

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <Routes>
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<p>Home</p>} />
                </Route>
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </ThemeProvider>,
    );

    expect(await screen.findByRole('link', { name: /users/i })).toBeInTheDocument();
  });
});
