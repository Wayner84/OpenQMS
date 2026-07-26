import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import { clearToken } from '../../shared/auth/tokenStore';
import { fetchCurrentUser, login } from './api';
import { AuthProvider } from './AuthContext';
import { LoginPage } from './LoginPage';

vi.mock('./api');

const mockedLogin = vi.mocked(login);
const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);

function renderLoginPage(): void {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>Dashboard</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
    clearToken();
  });

  it('submits the entered credentials and navigates to the dashboard on success', async () => {
    mockedFetchCurrentUser.mockRejectedValue(new Error('no token'));
    mockedLogin.mockResolvedValue({
      access_token: 'a.jwt.token',
      token_type: 'bearer',
      user: {
        id: 'u1',
        organisation_id: 'o1',
        email: 'ada@example.com',
        full_name: 'Ada Lovelace',
        role: 'member',
        is_active: true,
      },
    });

    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeEnabled();
    });

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'ada@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });
    expect(mockedLogin).toHaveBeenCalledWith({ email: 'ada@example.com', password: 'secret' });
  });

  it('shows an inline error and stays on the form for a 401 response', async () => {
    mockedFetchCurrentUser.mockRejectedValue(new Error('no token'));
    mockedLogin.mockRejectedValue(new ApiError('unauthorized', 401));

    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeEnabled();
    });

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'ada@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /log in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect email or password/i);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it('shows a generic error for a non-ApiError failure (e.g. a network error)', async () => {
    mockedFetchCurrentUser.mockRejectedValue(new Error('no token'));
    mockedLogin.mockRejectedValue(new Error('network error'));

    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeEnabled();
    });

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'ada@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: /log in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i);
  });
});
