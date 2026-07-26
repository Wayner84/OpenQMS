import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import { createUser, listUsers, updateUser } from './api';
import { UsersPage } from './UsersPage';

vi.mock('./api');

const mockedListUsers = vi.mocked(listUsers);
const mockedCreateUser = vi.mocked(createUser);
const mockedUpdateUser = vi.mocked(updateUser);

const admin = {
  id: 'u1',
  organisation_id: 'o1',
  email: 'admin@example.com',
  full_name: 'Ada Admin',
  role: 'admin' as const,
  is_active: true,
};

const member = {
  id: 'u2',
  organisation_id: 'o1',
  email: 'member@example.com',
  full_name: 'Mel Member',
  role: 'member' as const,
  is_active: true,
};

describe('UsersPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the list of users', async () => {
    mockedListUsers.mockResolvedValue({ items: [admin, member], total: 2, limit: 20, offset: 0 });

    render(<UsersPage />);

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Ada Admin')).toBeInTheDocument();
    });
    expect(screen.getByText('Mel Member')).toBeInTheDocument();
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListUsers.mockRejectedValue(new Error('network error'));

    render(<UsersPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load users/i);
  });

  it('creates a user and refreshes the list', async () => {
    mockedListUsers.mockResolvedValueOnce({ items: [admin], total: 1, limit: 20, offset: 0 });
    mockedCreateUser.mockResolvedValue(member);
    mockedListUsers.mockResolvedValueOnce({
      items: [admin, member],
      total: 2,
      limit: 20,
      offset: 0,
    });

    render(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Ada Admin')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Mel Member' } });
    fireEvent.change(screen.getByLabelText(/^email/i), { target: { value: 'member@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByRole('button', { name: /create user/i }));

    await waitFor(() => {
      expect(screen.getByText('Mel Member')).toBeInTheDocument();
    });
    expect(mockedCreateUser).toHaveBeenCalledWith({
      email: 'member@example.com',
      full_name: 'Mel Member',
      password: 'secret123',
      role: 'member',
    });
    expect(mockedListUsers).toHaveBeenCalledTimes(2);
  });

  it('shows the server error inline when creating a user fails', async () => {
    mockedListUsers.mockResolvedValue({ items: [admin], total: 1, limit: 20, offset: 0 });
    mockedCreateUser.mockRejectedValue(
      new ApiError('conflict', 409, { detail: 'A user with that email already exists' }),
    );

    render(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Ada Admin')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Dup' } });
    fireEvent.change(screen.getByLabelText(/^email/i), { target: { value: 'admin@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByRole('button', { name: /create user/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i);
  });

  it('deactivates an active user', async () => {
    mockedListUsers.mockResolvedValueOnce({
      items: [admin, member],
      total: 2,
      limit: 20,
      offset: 0,
    });
    mockedUpdateUser.mockResolvedValue({ ...member, is_active: false });
    mockedListUsers.mockResolvedValueOnce({
      items: [admin, { ...member, is_active: false }],
      total: 2,
      limit: 20,
      offset: 0,
    });

    render(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Mel Member')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /deactivate mel member/i }));

    await waitFor(() => {
      expect(mockedUpdateUser).toHaveBeenCalledWith('u2', { is_active: false });
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /reactivate mel member/i })).toBeInTheDocument();
    });
  });

  it('reactivates an inactive user', async () => {
    const inactiveMember = { ...member, is_active: false };
    mockedListUsers.mockResolvedValueOnce({
      items: [admin, inactiveMember],
      total: 2,
      limit: 20,
      offset: 0,
    });
    mockedUpdateUser.mockResolvedValue({ ...member, is_active: true });
    mockedListUsers.mockResolvedValueOnce({
      items: [admin, member],
      total: 2,
      limit: 20,
      offset: 0,
    });

    render(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Mel Member')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /reactivate mel member/i }));

    await waitFor(() => {
      expect(mockedUpdateUser).toHaveBeenCalledWith('u2', { is_active: true });
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /deactivate mel member/i })).toBeInTheDocument();
    });
  });

  it('changes a user role', async () => {
    mockedListUsers.mockResolvedValueOnce({
      items: [admin, member],
      total: 2,
      limit: 20,
      offset: 0,
    });
    mockedUpdateUser.mockResolvedValue({ ...member, role: 'admin' });
    mockedListUsers.mockResolvedValueOnce({
      items: [admin, { ...member, role: 'admin' }],
      total: 2,
      limit: 20,
      offset: 0,
    });

    render(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Mel Member')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/role for mel member/i), {
      target: { value: 'admin' },
    });

    await waitFor(() => {
      expect(mockedUpdateUser).toHaveBeenCalledWith('u2', { role: 'admin' });
    });
    expect(mockedListUsers).toHaveBeenCalledTimes(2);
  });

  it('shows a generic error when updating a user fails with a non-API error', async () => {
    mockedListUsers.mockResolvedValue({ items: [admin, member], total: 2, limit: 20, offset: 0 });
    mockedUpdateUser.mockRejectedValue(new Error('network error'));

    render(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Mel Member')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /deactivate mel member/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not update the user/i);
  });

  it('shows the server guard message inline when an update is rejected', async () => {
    mockedListUsers.mockResolvedValue({ items: [admin], total: 1, limit: 20, offset: 0 });
    mockedUpdateUser.mockRejectedValue(
      new ApiError('conflict', 409, { detail: 'An admin cannot deactivate or demote themselves' }),
    );

    render(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Ada Admin')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /deactivate ada admin/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /cannot deactivate or demote themselves/i,
    );
    expect(screen.getByRole('button', { name: /deactivate ada admin/i })).toBeInTheDocument();
  });

  it('paginates using the total count', async () => {
    mockedListUsers.mockResolvedValueOnce({ items: [admin], total: 2, limit: 1, offset: 0 });
    mockedListUsers.mockResolvedValueOnce({ items: [member], total: 2, limit: 1, offset: 1 });

    render(<UsersPage pageSize={1} />);
    await waitFor(() => {
      expect(screen.getByText('Ada Admin')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByText('Mel Member')).toBeInTheDocument();
    });
    expect(mockedListUsers).toHaveBeenLastCalledWith({ limit: 1, offset: 1 });
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
  });
});
