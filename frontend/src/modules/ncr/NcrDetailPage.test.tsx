import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setToken } from '../../shared/auth/tokenStore';
import { fetchCurrentUser } from '../auth/api';
import { AuthProvider } from '../auth/AuthContext';
import type { User } from '../auth/types';
import { listDocuments } from '../documents/api';
import { listCompanies, listPeople } from '../people/api';
import { listProducts } from '../products/api';
import { listSuppliers } from '../suppliers/api';
import {
  createAction,
  createAttachment,
  deleteAttachment,
  deleteNcr,
  exportNcr,
  getInvestigationTool,
  getNcr,
  listActions,
  listAttachments,
  listStatusHistory,
  transitionNcr,
  updateAction,
  updateNcr,
  upsertInvestigationTool,
} from './api';
import { NcrDetailPage } from './NcrDetailPage';

vi.mock('./api');
vi.mock('../auth/api');
vi.mock('../people/api');
vi.mock('../products/api');
vi.mock('../suppliers/api');
vi.mock('../documents/api');

const mockedGetNcr = vi.mocked(getNcr);
const mockedUpdateNcr = vi.mocked(updateNcr);
const mockedTransitionNcr = vi.mocked(transitionNcr);
const mockedListStatusHistory = vi.mocked(listStatusHistory);
const mockedListActions = vi.mocked(listActions);
const mockedCreateAction = vi.mocked(createAction);
const mockedUpdateAction = vi.mocked(updateAction);
const mockedGetInvestigationTool = vi.mocked(getInvestigationTool);
const mockedUpsertInvestigationTool = vi.mocked(upsertInvestigationTool);
const mockedListAttachments = vi.mocked(listAttachments);
const mockedCreateAttachment = vi.mocked(createAttachment);
const mockedDeleteAttachment = vi.mocked(deleteAttachment);
const mockedExportNcr = vi.mocked(exportNcr);
const mockedDeleteNcr = vi.mocked(deleteNcr);
const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);
const mockedListPeople = vi.mocked(listPeople);
const mockedListProducts = vi.mocked(listProducts);
const mockedListSuppliers = vi.mocked(listSuppliers);
const mockedListCompanies = vi.mocked(listCompanies);
const mockedListDocuments = vi.mocked(listDocuments);

const memberUser: User = {
  id: 'u1',
  organisation_id: 'o1',
  email: 'member@example.com',
  full_name: 'Member User',
  role: 'member',
  is_active: true,
};
const adminUser: User = { ...memberUser, id: 'u2', email: 'admin@example.com', role: 'admin' };

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

const ncrFixture = {
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

const emptyTool = {
  id: null,
  ncr_id: 'n1',
  tool_type: 'five_why' as const,
  data: {},
  created_by_id: null,
  updated_by_id: null,
  updated_at: null,
};

function renderPage(ncrId = 'n1'): ReturnType<typeof render> {
  setToken('a.jwt.token');
  return render(
    <MemoryRouter initialEntries={[`/ncr/${ncrId}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/ncr/:id" element={<NcrDetailPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('NcrDetailPage', () => {
  beforeEach(() => {
    mockedFetchCurrentUser.mockResolvedValue(memberUser);
    mockedListPeople.mockResolvedValue({ items: [quinn], total: 1, limit: 200, offset: 0 });
    mockedListProducts.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListSuppliers.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListCompanies.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedGetNcr.mockResolvedValue(ncrFixture);
    mockedListStatusHistory.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListActions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListAttachments.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedGetInvestigationTool.mockImplementation((ncrId, toolType) =>
      Promise.resolve({ ...emptyTool, ncr_id: ncrId, tool_type: toolType }),
    );
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the NCR metadata', async () => {
    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /NCR-0001/ })).toBeInTheDocument();
    });
    expect(screen.getByText(/status: open/i)).toBeInTheDocument();
    expect(screen.getByText(/raised by: quinn reporter/i)).toBeInTheDocument();
  });

  it('loads under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/ncr/n1']}>
          <AuthProvider>
            <Routes>
              <Route path="/ncr/:id" element={<NcrDetailPage />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /NCR-0001/ })).toBeInTheDocument();
    });
  });

  it('shows an error message when the NCR fails to load', async () => {
    mockedGetNcr.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load this ncr/i);
  });

  it('edits NCR metadata', async () => {
    mockedUpdateNcr.mockResolvedValue({ ...ncrFixture, description: 'Updated description' });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /NCR-0001/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit details/i }));
    fireEvent.change(screen.getByLabelText(/^description$/i), {
      target: { value: 'Updated description' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mockedUpdateNcr).toHaveBeenCalledWith(
        'n1',
        expect.objectContaining({ description: 'Updated description' }),
      );
    });
  });

  it('advances the workflow to the next status', async () => {
    mockedTransitionNcr.mockResolvedValue({ ...ncrFixture, status: 'investigate' });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /advance to investigate/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /advance to investigate/i }));

    await waitFor(() => {
      expect(mockedTransitionNcr).toHaveBeenCalledWith(
        'n1',
        expect.objectContaining({ to_status: 'investigate' }),
      );
    });
  });

  it('adds an action', async () => {
    mockedCreateAction.mockResolvedValue({
      id: 'a1',
      ncr_id: 'n1',
      description: 'Quarantine the batch',
      owner_id: null,
      due_date: null,
      status: 'open',
      completed_at: null,
      created_by_id: 'u1',
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/action description/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/action description/i), {
      target: { value: 'Quarantine the batch' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^add action$/i }));

    await waitFor(() => {
      expect(mockedCreateAction).toHaveBeenCalledWith(
        'n1',
        expect.objectContaining({ description: 'Quarantine the batch' }),
      );
    });
  });

  it('completes an open action', async () => {
    mockedListActions.mockResolvedValue({
      items: [
        {
          id: 'a1',
          ncr_id: 'n1',
          description: 'Quarantine the batch',
          owner_id: null,
          due_date: null,
          status: 'open',
          completed_at: null,
          created_by_id: 'u1',
        },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedUpdateAction.mockResolvedValue({
      id: 'a1',
      ncr_id: 'n1',
      description: 'Quarantine the batch',
      owner_id: null,
      due_date: null,
      status: 'complete',
      completed_at: '2026-07-30T00:00:00Z',
      created_by_id: 'u1',
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Quarantine the batch')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^complete$/i }));

    await waitFor(() => {
      expect(mockedUpdateAction).toHaveBeenCalledWith(
        'a1',
        expect.objectContaining({ status: 'complete' }),
      );
    });
  });

  it('saves an investigation tool worksheet', async () => {
    mockedUpsertInvestigationTool.mockResolvedValue({
      id: 't1',
      ncr_id: 'n1',
      tool_type: 'five_why',
      data: { why_1: 'The seal failed' },
      created_by_id: 'u1',
      updated_by_id: 'u1',
      updated_at: '2026-07-30T00:00:00Z',
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add field/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /add field/i }));
    fireEvent.change(screen.getByLabelText(/field/i), { target: { value: 'why_1' } });
    fireEvent.change(screen.getByLabelText(/^value$/i), { target: { value: 'The seal failed' } });
    fireEvent.click(screen.getByRole('button', { name: /save worksheet/i }));

    await waitFor(() => {
      expect(mockedUpsertInvestigationTool).toHaveBeenCalledWith('n1', 'five_why', {
        why_1: 'The seal failed',
      });
    });
  });

  it('attaches a document found by search', async () => {
    mockedListDocuments.mockResolvedValue({
      items: [
        {
          id: 'd1',
          organisation_id: 'o1',
          category_id: null,
          number: 'DOC-0001',
          title: 'Inspection photo',
          owner_id: null,
          status: 'draft',
          current_version_id: null,
          created_by_id: 'u1',
          updated_by_id: 'u1',
          tags: [],
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });
    mockedCreateAttachment.mockResolvedValue({
      id: 'att1',
      ncr_id: 'n1',
      document_id: 'd1',
      description: null,
      created_by_id: 'u1',
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/^search documents$/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^search documents$/i), {
      target: { value: 'inspection' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/^document$/i)).toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText(/^document$/i), { target: { value: 'd1' } });
    fireEvent.click(screen.getByRole('button', { name: /attach document/i }));

    await waitFor(() => {
      expect(mockedCreateAttachment).toHaveBeenCalledWith(
        'n1',
        expect.objectContaining({ document_id: 'd1' }),
      );
    });
  });

  it('removes an existing attachment', async () => {
    mockedListAttachments.mockResolvedValue({
      items: [
        { id: 'att1', ncr_id: 'n1', document_id: 'd1', description: 'Defect photo', created_by_id: 'u1' },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedDeleteAttachment.mockResolvedValue(undefined);

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Defect photo')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^remove$/i }));

    await waitFor(() => {
      expect(mockedDeleteAttachment).toHaveBeenCalledWith('n1', 'att1');
    });
  });

  it('exports the NCR as a PDF', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    mockedExportNcr.mockResolvedValue(new Blob(['%PDF-1.7']));

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /export pdf/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /export pdf/i }));

    await waitFor(() => {
      expect(mockedExportNcr).toHaveBeenCalledWith('n1');
      expect(clickSpy).toHaveBeenCalledOnce();
    });
  });

  it('does not show the delete button for a non-admin', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /NCR-0001/ })).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /delete ncr/i })).not.toBeInTheDocument();
  });

  it('lets an admin delete the NCR after confirming', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedDeleteNcr.mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderPage();
    const deleteButton = await screen.findByRole('button', { name: /delete ncr/i });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockedDeleteNcr).toHaveBeenCalledWith('n1');
    });
  });
});
