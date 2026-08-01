import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listCompanies, listPeople } from '../people/api';
import { listProducts } from '../products/api';
import { listSuppliers } from '../suppliers/api';
import { createNcr, listNcrs } from './api';
import { NcrsPage } from './NcrsPage';

vi.mock('./api');
vi.mock('../people/api');
vi.mock('../products/api');
vi.mock('../suppliers/api');

const mockedListNcrs = vi.mocked(listNcrs);
const mockedCreateNcr = vi.mocked(createNcr);
const mockedListPeople = vi.mocked(listPeople);
const mockedListProducts = vi.mocked(listProducts);
const mockedListSuppliers = vi.mocked(listSuppliers);
const mockedListCompanies = vi.mocked(listCompanies);

const quinn = {
  id: 'p1',
  organisation_id: 'o1',
  company_id: null,
  first_name: 'Quinn',
  last_name: 'Reporter',
  email: null,
  phone: null,
  role: null,
  department: null,
  notes: null,
  is_employee: true,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const ncr = {
  id: 'n1',
  organisation_id: 'o1',
  number: 'NCR-0001',
  type: 'internal' as const,
  product_id: null,
  supplier_id: null,
  status: 'open' as const,
  raised_by_id: 'p1',
  description: 'A widget was out of spec',
  root_cause_summary: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
  closed_at: null,
};

function renderPage(pageSize?: number): ReturnType<typeof render> {
  return render(
    <MemoryRouter>
      <NcrsPage pageSize={pageSize} />
    </MemoryRouter>,
  );
}

describe('NcrsPage', () => {
  beforeEach(() => {
    mockedListPeople.mockResolvedValue({ items: [quinn], total: 1, limit: 200, offset: 0 });
    mockedListProducts.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListSuppliers.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListCompanies.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the list of NCRs', async () => {
    mockedListNcrs.mockResolvedValue({ items: [ncr], total: 1, limit: 20, offset: 0 });

    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'NCR-0001' })).toBeInTheDocument();
    });
    expect(screen.getByText('A widget was out of spec')).toBeInTheDocument();
  });

  it('loads the list under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    mockedListNcrs.mockResolvedValue({ items: [ncr], total: 1, limit: 20, offset: 0 });

    render(
      <StrictMode>
        <MemoryRouter>
          <NcrsPage />
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'NCR-0001' })).toBeInTheDocument();
    });
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListNcrs.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load ncrs/i);
  });

  it('creates an internal NCR without a supplier picker', async () => {
    mockedListNcrs.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreateNcr.mockResolvedValue(ncr);
    mockedListNcrs.mockResolvedValueOnce({ items: [ncr], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/raised by/i)).toBeInTheDocument();
    });

    expect(screen.queryByLabelText(/^supplier$/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/raised by/i), { target: { value: 'p1' } });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: 'A widget was out of spec' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^create ncr$/i }));

    await waitFor(() => {
      expect(mockedCreateNcr).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'internal',
          raised_by_id: 'p1',
          description: 'A widget was out of spec',
          supplier_id: undefined,
        }),
      );
    });
  });

  it('requires a supplier when the type is switched to supplier', async () => {
    mockedListNcrs.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/^type$/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^type$/i), { target: { value: 'supplier' } });

    expect(await screen.findByLabelText(/^supplier$/i)).toBeRequired();
  });

  it('searches NCRs by number or description', async () => {
    mockedListNcrs.mockResolvedValue({ items: [ncr], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'NCR-0001' })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^search$/i), { target: { value: 'widget' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      expect(mockedListNcrs).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'widget' }),
      );
    });
  });

  it('paginates using the total count', async () => {
    const second = { ...ncr, id: 'n2', number: 'NCR-0002' };
    mockedListNcrs.mockResolvedValueOnce({ items: [ncr], total: 2, limit: 1, offset: 0 });
    mockedListNcrs.mockResolvedValueOnce({ items: [second], total: 2, limit: 1, offset: 1 });

    renderPage(1);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'NCR-0001' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'NCR-0002' })).toBeInTheDocument();
    });
  });
});
