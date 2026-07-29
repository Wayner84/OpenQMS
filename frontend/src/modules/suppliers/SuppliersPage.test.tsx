import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listCompanies } from '../people/api';
import { createSupplier, listSuppliers } from './api';
import { SuppliersPage } from './SuppliersPage';

vi.mock('./api');
vi.mock('../people/api');

const mockedListSuppliers = vi.mocked(listSuppliers);
const mockedCreateSupplier = vi.mocked(createSupplier);
const mockedListCompanies = vi.mocked(listCompanies);

const acmeCompany = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Acme Ltd',
  type: 'supplier' as const,
  address: null,
  phone: null,
  general_email: null,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const acmeSupplier = {
  id: 's1',
  organisation_id: 'o1',
  company_id: 'c1',
  approval_status: 'approved' as const,
  risk_rating: 'low' as const,
  is_preferred: true,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

function renderPage(pageSize?: number): ReturnType<typeof render> {
  return render(
    <MemoryRouter>
      <SuppliersPage pageSize={pageSize} />
    </MemoryRouter>,
  );
}

describe('SuppliersPage', () => {
  beforeEach(() => {
    mockedListCompanies.mockResolvedValue({
      items: [acmeCompany],
      total: 1,
      limit: 200,
      offset: 0,
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the list of suppliers', async () => {
    mockedListSuppliers.mockResolvedValue({
      items: [acmeSupplier],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Acme Ltd' })).toBeInTheDocument();
    });
    const row = screen.getByRole('link', { name: 'Acme Ltd' }).closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText('Approved')).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('Low')).toBeInTheDocument();
  });

  it('loads the list under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    mockedListSuppliers.mockResolvedValue({
      items: [acmeSupplier],
      total: 1,
      limit: 20,
      offset: 0,
    });

    render(
      <StrictMode>
        <MemoryRouter>
          <SuppliersPage />
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Acme Ltd' })).toBeInTheDocument();
    });
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListSuppliers.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load suppliers/i);
  });

  it('prompts to create a company first when none exist', async () => {
    mockedListCompanies.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListSuppliers.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();

    expect(await screen.findByText(/create a company first/i)).toBeInTheDocument();
  });

  it('creates a supplier and refreshes the list', async () => {
    mockedListSuppliers.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreateSupplier.mockResolvedValue(acmeSupplier);
    mockedListSuppliers.mockResolvedValueOnce({
      items: [acmeSupplier],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/^company/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^company/i), { target: { value: 'c1' } });
    fireEvent.click(screen.getByRole('button', { name: /^create supplier$/i }));

    await waitFor(() => {
      expect(mockedCreateSupplier).toHaveBeenCalledWith(
        expect.objectContaining({ company_id: 'c1', approval_status: 'pending' }),
      );
    });
  });

  it('searches suppliers by the linked company name', async () => {
    mockedListSuppliers.mockResolvedValue({
      items: [acmeSupplier],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Acme Ltd' })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^search$/i), { target: { value: 'acme' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      expect(mockedListSuppliers).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'acme' }),
      );
    });
  });

  it('paginates using the total count', async () => {
    const secondSupplier = { ...acmeSupplier, id: 's2', company_id: 'c2' };
    mockedListCompanies.mockResolvedValue({
      items: [acmeCompany, { ...acmeCompany, id: 'c2', name: 'Globex Inc' }],
      total: 2,
      limit: 200,
      offset: 0,
    });
    mockedListSuppliers.mockResolvedValueOnce({
      items: [acmeSupplier],
      total: 2,
      limit: 1,
      offset: 0,
    });
    mockedListSuppliers.mockResolvedValueOnce({
      items: [secondSupplier],
      total: 2,
      limit: 1,
      offset: 1,
    });

    renderPage(1);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Acme Ltd' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Globex Inc' })).toBeInTheDocument();
    });
  });
});
