import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import { createCompany, deleteCompany, listCompanies, updateCompany } from './api';
import { CompaniesPage } from './CompaniesPage';

vi.mock('./api');

const mockedListCompanies = vi.mocked(listCompanies);
const mockedCreateCompany = vi.mocked(createCompany);
const mockedUpdateCompany = vi.mocked(updateCompany);
const mockedDeleteCompany = vi.mocked(deleteCompany);

const acme = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Acme Ltd',
  type: 'customer' as const,
  address: null,
  phone: null,
  general_email: null,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const globex = {
  id: 'c2',
  organisation_id: 'o1',
  name: 'Globex Inc',
  type: 'supplier' as const,
  address: null,
  phone: null,
  general_email: null,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

function renderPage(pageSize?: number): ReturnType<typeof render> {
  return render(
    <MemoryRouter>
      <CompaniesPage pageSize={pageSize} />
    </MemoryRouter>,
  );
}

describe('CompaniesPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the list of companies', async () => {
    mockedListCompanies.mockResolvedValue({
      items: [acme, globex],
      total: 2,
      limit: 20,
      offset: 0,
    });

    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
    });
    expect(screen.getByText('Globex Inc')).toBeInTheDocument();
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListCompanies.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load companies/i);
  });

  it('creates a company and refreshes the list', async () => {
    mockedListCompanies.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreateCompany.mockResolvedValue(acme);
    mockedListCompanies.mockResolvedValueOnce({ items: [acme], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(mockedListCompanies).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/^name/i), { target: { value: 'Acme Ltd' } });
    fireEvent.change(screen.getByLabelText(/^type/i), { target: { value: 'customer' } });
    fireEvent.click(screen.getByRole('button', { name: /create company/i }));

    await waitFor(() => {
      expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
    });
    expect(mockedCreateCompany).toHaveBeenCalledWith({
      name: 'Acme Ltd',
      type: 'customer',
      address: undefined,
      phone: undefined,
      general_email: undefined,
      notes: undefined,
    });
  });

  it('omits a blank general email rather than sending an empty string (which the backend rejects as an invalid address)', async () => {
    mockedListCompanies.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreateCompany.mockResolvedValue(acme);
    mockedListCompanies.mockResolvedValueOnce({ items: [acme], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(mockedListCompanies).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/^name/i), { target: { value: 'Acme Ltd' } });
    fireEvent.click(screen.getByRole('button', { name: /create company/i }));

    await waitFor(() => {
      expect(mockedCreateCompany).toHaveBeenCalledOnce();
    });
    expect(mockedCreateCompany).toHaveBeenCalledWith(
      expect.objectContaining({ general_email: undefined }),
    );
  });

  it('edits a company and refreshes the list', async () => {
    mockedListCompanies.mockResolvedValueOnce({ items: [acme], total: 1, limit: 20, offset: 0 });
    mockedUpdateCompany.mockResolvedValue({ ...acme, name: 'Acme Corp' });
    mockedListCompanies.mockResolvedValueOnce({
      items: [{ ...acme, name: 'Acme Corp' }],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit acme ltd/i }));
    fireEvent.change(screen.getByLabelText(/^name/i), { target: { value: 'Acme Corp' } });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });
    expect(mockedUpdateCompany).toHaveBeenCalledWith(
      'c1',
      expect.objectContaining({ name: 'Acme Corp' }),
    );
  });

  it('deletes a company and refreshes the list', async () => {
    mockedListCompanies.mockResolvedValueOnce({
      items: [acme, globex],
      total: 2,
      limit: 20,
      offset: 0,
    });
    mockedDeleteCompany.mockResolvedValue(undefined);
    mockedListCompanies.mockResolvedValueOnce({ items: [globex], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete acme ltd/i }));

    await waitFor(() => {
      expect(screen.queryByText('Acme Ltd')).not.toBeInTheDocument();
    });
    expect(mockedDeleteCompany).toHaveBeenCalledWith('c1');
  });

  it('paginates using the total count', async () => {
    mockedListCompanies.mockResolvedValueOnce({ items: [acme], total: 2, limit: 1, offset: 0 });
    mockedListCompanies.mockResolvedValueOnce({ items: [globex], total: 2, limit: 1, offset: 1 });

    renderPage(1);
    await waitFor(() => {
      expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /next/i })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByText('Globex Inc')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
  });

  it('shows the server conflict message inline when deleting a company with contacts fails', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 20, offset: 0 });
    mockedDeleteCompany.mockRejectedValue(
      new ApiError('conflict', 409, { detail: 'Cannot delete a company with existing contacts' }),
    );

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete acme ltd/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/existing contacts/i);
    expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
  });

  it('links to the contacts view for a company', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Acme Ltd')).toBeInTheDocument();
    });

    expect(screen.getByRole('link', { name: /view contacts for acme ltd/i })).toHaveAttribute(
      'href',
      '/people?company=c1',
    );
  });
});
