import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchCurrentUser } from '../auth/api';
import { AuthProvider } from '../auth/AuthContext';
import type { User } from '../auth/types';
import { clearToken, setToken } from '../../shared/auth/tokenStore';
import { listPeople } from '../people/api';
import type { Person } from '../people/types';
import { createDocument, listCategories, listDocuments, listTags } from './api';
import { DocumentsPage } from './DocumentsPage';

vi.mock('./api');
vi.mock('../auth/api');
vi.mock('../people/api');

const mockedListDocuments = vi.mocked(listDocuments);
const mockedListCategories = vi.mocked(listCategories);
const mockedListTags = vi.mocked(listTags);
const mockedListPeople = vi.mocked(listPeople);
const mockedCreateDocument = vi.mocked(createDocument);
const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);

const memberUser: User = {
  id: 'u1',
  organisation_id: 'o1',
  email: 'member@example.com',
  full_name: 'Member User',
  role: 'member',
  is_active: true,
};

const adminUser: User = { ...memberUser, id: 'u2', email: 'admin@example.com', role: 'admin' };

const qualityManual = {
  id: 'd1',
  organisation_id: 'o1',
  category_id: null,
  number: 'DOC-0001',
  title: 'Quality Manual',
  owner_id: null,
  status: 'draft' as const,
  current_version_id: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
  tags: [],
};

const weldingProcedure = {
  id: 'd2',
  organisation_id: 'o1',
  category_id: null,
  number: 'DOC-0002',
  title: 'Welding Procedure',
  owner_id: 'p1',
  status: 'approved' as const,
  current_version_id: 'v1',
  created_by_id: 'u1',
  updated_by_id: 'u1',
  tags: [],
};

const qualityCategory = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Quality',
  parent_category_id: null,
};

/** A promise plus its resolvers, for tests that need precise control over when a
 * mocked API call settles -- used to prove an out-of-order (slower, earlier)
 * options response can't overwrite a newer one. */
function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
} {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

const ownerPerson: Person = {
  id: 'p1',
  organisation_id: 'o1',
  company_id: null,
  first_name: 'Jane',
  last_name: 'Doe',
  email: null,
  phone: null,
  role: null,
  department: null,
  notes: null,
  is_employee: true,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

function renderPage(pageSize?: number): ReturnType<typeof render> {
  setToken('a.jwt.token');
  return render(
    <MemoryRouter>
      <AuthProvider>
        <DocumentsPage pageSize={pageSize} />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('DocumentsPage', () => {
  beforeEach(() => {
    mockedFetchCurrentUser.mockResolvedValue(memberUser);
    mockedListPeople.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
  });

  afterEach(() => {
    vi.resetAllMocks();
    clearToken();
  });

  it('shows a loading state, then the list of documents', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({
      items: [qualityManual, weldingProcedure],
      total: 2,
      limit: 20,
      offset: 0,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Quality Manual')).toBeInTheDocument();
    });
    expect(screen.getByText('Welding Procedure')).toBeInTheDocument();
  });

  it('loads the list under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({
      items: [qualityManual],
      total: 1,
      limit: 20,
      offset: 0,
    });
    setToken('a.jwt.token');

    render(
      <StrictMode>
        <MemoryRouter>
          <AuthProvider>
            <DocumentsPage />
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByText('Quality Manual')).toBeInTheDocument();
    });
  });

  it('shows an empty state when there are no documents', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load documents/i);
  });

  it('creates a document and refreshes the list', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreateDocument.mockResolvedValue(qualityManual);
    mockedListDocuments.mockResolvedValueOnce({
      items: [qualityManual],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/^title$/i), { target: { value: 'Quality Manual' } });
    fireEvent.click(screen.getByRole('button', { name: /^create document$/i }));

    await waitFor(() => {
      expect(screen.getByText('Quality Manual')).toBeInTheDocument();
    });
    expect(mockedCreateDocument).toHaveBeenCalledWith({
      title: 'Quality Manual',
      category_id: undefined,
      tag_ids: [],
    });
  });

  it('refreshes using the current filters after create, not a stale closure captured when Create was clicked', async () => {
    const categoryAlpha = {
      id: 'c1',
      organisation_id: 'o1',
      name: 'Alpha',
      parent_category_id: null,
    };
    const categoryBeta = {
      id: 'c2',
      organisation_id: 'o1',
      name: 'Beta',
      parent_category_id: null,
    };
    mockedListCategories.mockResolvedValue({
      items: [categoryAlpha, categoryBeta],
      total: 2,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    const createDeferred = deferred<typeof qualityManual>();
    mockedCreateDocument.mockReturnValue(createDeferred.promise);

    renderPage();
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenCalledTimes(1);
    });

    // Filter to "Alpha", then start creating a document while that filter is active.
    fireEvent.change(screen.getByLabelText(/filter by category/i), { target: { value: 'c1' } });
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ categoryId: 'c1' }),
      );
    });

    fireEvent.change(screen.getByLabelText(/^title$/i), { target: { value: 'Quality Manual' } });
    fireEvent.click(screen.getByRole('button', { name: /^create document$/i }));

    // While the create request is still in flight, the filter changes to "Beta".
    fireEvent.change(screen.getByLabelText(/filter by category/i), { target: { value: 'c2' } });
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ categoryId: 'c2' }),
      );
    });

    createDeferred.resolve(qualityManual);
    await waitFor(() => {
      expect(mockedCreateDocument).toHaveBeenCalled();
    });

    // The post-create refresh must use the filter current at the time it actually
    // runs ("Beta") -- not the filter that was active back when Create was first
    // clicked ("Alpha"), which a stale closure over `loadPage` would incorrectly
    // send.
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ categoryId: 'c2' }),
      );
    });
  });

  it('searches by title/number', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({
      items: [qualityManual],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/^search$/i), { target: { value: 'quality' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'quality' }),
      );
    });
  });

  it('paginates using the total count', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValueOnce({
      items: [qualityManual],
      total: 2,
      limit: 1,
      offset: 0,
    });
    mockedListDocuments.mockResolvedValueOnce({
      items: [weldingProcedure],
      total: 2,
      limit: 1,
      offset: 1,
    });

    renderPage(1);
    await waitFor(() => {
      expect(screen.getByText('Quality Manual')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /next/i })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByText('Welding Procedure')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
  });

  it('shows a link to manage categories and tags only for an admin', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();

    expect(
      await screen.findByRole('link', { name: /manage categories & tags/i }),
    ).toBeInTheDocument();
  });

  it('does not show a link to manage categories and tags for a non-admin', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();

    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenCalled();
    });
    expect(
      screen.queryByRole('link', { name: /manage categories & tags/i }),
    ).not.toBeInTheDocument();
  });

  it("shows an owner column resolving owner_id to the person's name", async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [ownerPerson], total: 1, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({
      items: [qualityManual, weldingProcedure],
      total: 2,
      limit: 20,
      offset: 0,
    });

    renderPage();

    // Not `findByText`: "Jane Doe" also appears as an `<option>` in the "Filter by
    // owner" select once any owner exists, which `findByText` would match too and
    // make the query ambiguous.
    expect(await screen.findByRole('cell', { name: 'Jane Doe' })).toBeInTheDocument();
  });

  it('filters documents by owner', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [ownerPerson], total: 1, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({
      items: [weldingProcedure],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/filter by owner/i), { target: { value: 'p1' } });

    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ ownerId: 'p1' }),
      );
    });
  });

  it('refreshes after create with the latest filters rather than the filters captured when creation began', async () => {
    const pendingCreate = deferred<typeof qualityManual>();
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreateDocument.mockReturnValue(pendingCreate.promise);

    renderPage();
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/^title$/i), { target: { value: 'New document' } });
    fireEvent.submit(screen.getByRole('form', { name: /create document/i }));
    await waitFor(() => {
      expect(mockedCreateDocument).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/filter by status/i), {
      target: { value: 'approved' },
    });
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'approved' }),
      );
    });

    pendingCreate.resolve(qualityManual);
    await waitFor(() => {
      expect(mockedListDocuments).toHaveBeenCalledTimes(3);
    });
    expect(mockedListDocuments).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'approved' }),
    );
  });

  it('does not let a stale, out-of-order category options response (StrictMode double-invoke) overwrite a fresher one', async () => {
    // React 18 StrictMode double-invokes the mount effect (mount, cleanup, mount
    // again) synchronously, so both option-loading calls dispatch their requests
    // before either resolves -- exactly the shape of a real out-of-order-response
    // race, and reproducible without any real network timing.
    const staleCategories = deferred<{
      items: (typeof qualityCategory)[];
      total: number;
      limit: number;
      offset: number;
    }>();
    mockedListCategories.mockReturnValueOnce(staleCategories.promise);
    mockedListCategories.mockResolvedValueOnce({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListDocuments.mockResolvedValue({
      items: [{ ...qualityManual, category_id: 'c1' }],
      total: 1,
      limit: 20,
      offset: 0,
    });

    render(
      <StrictMode>
        <MemoryRouter>
          <AuthProvider>
            <DocumentsPage />
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>,
    );

    expect(await screen.findByRole('cell', { name: 'Quality' })).toBeInTheDocument();

    // The first (StrictMode-simulated, discarded) invocation's response finally
    // arrives, empty -- it must not overwrite the second invocation's data, which
    // is already showing (as the resolved category name, not the raw id).
    staleCategories.resolve({ items: [], total: 0, limit: 200, offset: 0 });
    await new Promise((resolve) => {
      setTimeout(resolve, 0);
    });

    expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
  });

  it('shows an error message when the owner options fail to load, without breaking the document list', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListPeople.mockRejectedValue(new Error('network error'));
    mockedListDocuments.mockResolvedValue({
      items: [qualityManual],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
    expect(await screen.findByText('Quality Manual')).toBeInTheDocument();
  });
});
