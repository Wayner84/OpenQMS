import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import { createPerson, deletePerson, listCompanies, listPeople, updatePerson } from './api';
import { PeoplePage } from './PeoplePage';

vi.mock('./api');

const mockedListPeople = vi.mocked(listPeople);
const mockedCreatePerson = vi.mocked(createPerson);
const mockedUpdatePerson = vi.mocked(updatePerson);
const mockedDeletePerson = vi.mocked(deletePerson);
const mockedListCompanies = vi.mocked(listCompanies);

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

const ada = {
  id: 'p1',
  organisation_id: 'o1',
  company_id: null,
  first_name: 'Ada',
  last_name: 'Lovelace',
  email: 'ada@example.com',
  phone: null,
  role: null,
  department: null,
  notes: null,
  is_employee: true,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const grace = {
  id: 'p2',
  organisation_id: 'o1',
  company_id: 'c1',
  first_name: 'Grace',
  last_name: 'Hopper',
  email: 'grace@acme.example.com',
  phone: null,
  role: 'Buyer',
  department: null,
  notes: null,
  is_employee: false,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

function renderPage(
  initialEntries: string[] = ['/people'],
  pageSize?: number,
): ReturnType<typeof render> {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <PeoplePage pageSize={pageSize} />
    </MemoryRouter>,
  );
}

describe('PeoplePage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the list of people', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [ada, grace], total: 2, limit: 20, offset: 0 });

    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    });
    expect(screen.getByText('Grace Hopper')).toBeInTheDocument();
  });

  it('loads the list under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    // See the equivalent test in UsersPage.test.tsx for why plain `render` doesn't
    // exercise this path but the real (dev-mode) browser does.
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [ada, grace], total: 2, limit: 20, offset: 0 });

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/people']}>
          <PeoplePage />
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    });
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListCompanies.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListPeople.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load people/i);
  });

  it('creates an employee with no company', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreatePerson.mockResolvedValue(ada);
    mockedListPeople.mockResolvedValueOnce({ items: [ada], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(mockedListPeople).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Ada' } });
    fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: 'Lovelace' } });
    fireEvent.click(screen.getByLabelText(/is an employee/i));
    fireEvent.click(screen.getByRole('button', { name: /create person/i }));

    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    });
    expect(mockedCreatePerson).toHaveBeenCalledWith(
      expect.objectContaining({
        first_name: 'Ada',
        last_name: 'Lovelace',
        is_employee: true,
        company_id: null,
      }),
    );
  });

  it('creates a contact linked to a company', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreatePerson.mockResolvedValue(grace);
    mockedListPeople.mockResolvedValueOnce({ items: [grace], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/company/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Grace' } });
    fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: 'Hopper' } });
    fireEvent.change(screen.getByLabelText(/company/i), { target: { value: 'c1' } });
    fireEvent.click(screen.getByRole('button', { name: /create person/i }));

    await waitFor(() => {
      expect(screen.getByText('Grace Hopper')).toBeInTheDocument();
    });
    expect(mockedCreatePerson).toHaveBeenCalledWith(
      expect.objectContaining({
        first_name: 'Grace',
        last_name: 'Hopper',
        is_employee: false,
        company_id: 'c1',
      }),
    );
  });

  it('edits a person', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValueOnce({ items: [ada], total: 1, limit: 20, offset: 0 });
    mockedUpdatePerson.mockResolvedValue({ ...ada, role: 'Engineer' });
    mockedListPeople.mockResolvedValueOnce({
      items: [{ ...ada, role: 'Engineer' }],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit ada lovelace/i }));
    fireEvent.change(screen.getByLabelText(/^role/i), { target: { value: 'Engineer' } });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mockedUpdatePerson).toHaveBeenCalledWith(
        'p1',
        expect.objectContaining({ role: 'Engineer' }),
      );
    });
  });

  it('switches an existing contact to an employee while editing, clearing the company', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValueOnce({ items: [grace], total: 1, limit: 20, offset: 0 });
    mockedUpdatePerson.mockResolvedValue({ ...grace, is_employee: true, company_id: null });
    mockedListPeople.mockResolvedValueOnce({
      items: [{ ...grace, is_employee: true, company_id: null }],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Grace Hopper')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit grace hopper/i }));
    expect(screen.getByLabelText(/company/i)).toHaveValue('c1');
    fireEvent.click(screen.getByLabelText(/is an employee/i));
    expect(screen.queryByLabelText(/company/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mockedUpdatePerson).toHaveBeenCalledWith(
        'p2',
        expect.objectContaining({ is_employee: true, company_id: null }),
      );
    });
  });

  it('requires selecting a company to create a contact when none exist yet', async () => {
    mockedListCompanies.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/company/i)).toBeInTheDocument();
    });

    const companySelect = screen.getByLabelText(/company/i);
    expect(companySelect).toBeRequired();
    expect(screen.getAllByRole('option')).toHaveLength(1);

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Grace' } });
    fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: 'Hopper' } });
    fireEvent.click(screen.getByRole('button', { name: /create person/i }));

    expect(mockedCreatePerson).not.toHaveBeenCalled();
  });

  it('paginates using the total count', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValueOnce({ items: [ada], total: 2, limit: 1, offset: 0 });
    mockedListPeople.mockResolvedValueOnce({ items: [grace], total: 2, limit: 1, offset: 1 });

    renderPage(['/people'], 1);
    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /next/i })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByText('Grace Hopper')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
  });

  it('deletes a person', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValueOnce({ items: [ada], total: 1, limit: 20, offset: 0 });
    mockedDeletePerson.mockResolvedValue(undefined);
    mockedListPeople.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete ada lovelace/i }));

    await waitFor(() => {
      expect(screen.queryByText('Ada Lovelace')).not.toBeInTheDocument();
    });
    expect(mockedDeletePerson).toHaveBeenCalledWith('p1');
  });

  it('searches people by name/email/role', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [ada], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(mockedListPeople).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByRole('searchbox', { name: /search people/i }), {
      target: { value: 'ada' },
    });
    fireEvent.submit(screen.getByRole('search'));

    await waitFor(() => {
      expect(mockedListPeople).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'ada' }));
    });
  });

  it('pre-filters to a company given a ?company= query param and shows a banner', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [grace], total: 1, limit: 20, offset: 0 });

    renderPage(['/people?company=c1']);

    await waitFor(() => {
      expect(mockedListPeople).toHaveBeenLastCalledWith(
        expect.objectContaining({ companyId: 'c1' }),
      );
    });
    expect(await screen.findByText(/showing contacts for acme ltd/i)).toBeInTheDocument();
  });

  it('shows the server error inline when creating a person fails', async () => {
    mockedListCompanies.mockResolvedValue({ items: [acme], total: 1, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreatePerson.mockRejectedValue(
      new ApiError('not found', 404, { detail: 'Company not found' }),
    );

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/company/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Grace' } });
    fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: 'Hopper' } });
    fireEvent.change(screen.getByLabelText(/company/i), { target: { value: 'c1' } });
    fireEvent.click(screen.getByRole('button', { name: /create person/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/company not found/i);
  });
});
