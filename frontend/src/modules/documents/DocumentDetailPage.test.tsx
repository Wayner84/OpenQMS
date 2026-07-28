import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import { fetchCurrentUser } from '../auth/api';
import { AuthProvider } from '../auth/AuthContext';
import type { User } from '../auth/types';
import { listPeople } from '../people/api';
import type { Person } from '../people/types';
import type { DocumentRecord } from './types';
import {
  acknowledgeVersion,
  approveVersion,
  deleteDocument,
  downloadDocumentVersion,
  getDocument,
  listCategories,
  listDocumentVersions,
  listTags,
  listVersionAcknowledgements,
  previewDocumentVersion,
  rejectVersion,
  retireDocument,
  submitVersionForApproval,
  updateDocument,
  uploadDocumentVersion,
} from './api';
import { DocumentDetailPage } from './DocumentDetailPage';

vi.mock('./api');
vi.mock('../auth/api');
vi.mock('../people/api');

const mockedGetDocument = vi.mocked(getDocument);
const mockedListDocumentVersions = vi.mocked(listDocumentVersions);
const mockedListCategories = vi.mocked(listCategories);
const mockedListTags = vi.mocked(listTags);
const mockedListPeople = vi.mocked(listPeople);
const mockedUploadDocumentVersion = vi.mocked(uploadDocumentVersion);
const mockedSubmitVersionForApproval = vi.mocked(submitVersionForApproval);
const mockedApproveVersion = vi.mocked(approveVersion);
const mockedRejectVersion = vi.mocked(rejectVersion);
const mockedAcknowledgeVersion = vi.mocked(acknowledgeVersion);
const mockedListVersionAcknowledgements = vi.mocked(listVersionAcknowledgements);
const mockedDownloadDocumentVersion = vi.mocked(downloadDocumentVersion);
const mockedPreviewDocumentVersion = vi.mocked(previewDocumentVersion);
const mockedRetireDocument = vi.mocked(retireDocument);
const mockedUpdateDocument = vi.mocked(updateDocument);
const mockedDeleteDocument = vi.mocked(deleteDocument);
const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);

/** A promise plus its resolvers, exposed for tests that need precise control over
 * when a mocked API call settles -- used to prove that an out-of-order (slower,
 * earlier) response can never clobber state a later request already applied. */
function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const memberUser: User = {
  id: 'u1',
  organisation_id: 'o1',
  email: 'member@example.com',
  full_name: 'Member User',
  role: 'member',
  is_active: true,
};
const adminUser: User = { ...memberUser, id: 'u2', email: 'admin@example.com', role: 'admin' };

const documentFixture = {
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

const draftVersion = {
  id: 'v1',
  document_id: 'd1',
  version_number: 1,
  original_filename: 'report.pdf',
  content_type: 'application/pdf',
  size_bytes: 100,
  checksum_sha256: 'abc',
  change_summary: null,
  status: 'draft' as const,
  created_by_id: 'u1',
  created_at: '2026-07-26T00:00:00Z',
};

const inReviewVersion = {
  ...draftVersion,
  id: 'v2',
  version_number: 2,
  status: 'in_review' as const,
};

const qualityCategory = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Quality',
  parent_category_id: null,
};

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

function renderPage(documentId = 'd1'): ReturnType<typeof render> {
  setToken('a.jwt.token');
  return render(
    <MemoryRouter initialEntries={[`/documents/${documentId}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

/** Renders the page with an extra "Go to {id}" button that navigates to a
 * different document id on the same mounted route, for tests that need to prove a
 * stale response from the *previous* id can't clobber the newer one -- a plain
 * `renderPage()` re-render can't exercise this because the component instance
 * (and its request-generation ref) must stay mounted across the navigation. */
function renderWithNavigationHarness(initialId: string): ReturnType<typeof render> {
  function Harness(): ReturnType<typeof DocumentDetailPage> {
    const navigate = useNavigate();
    return (
      <>
        <button
          type="button"
          onClick={() => {
            void navigate('/documents/d2');
          }}
        >
          Go to d2
        </button>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
        </Routes>
      </>
    );
  }

  setToken('a.jwt.token');
  return render(
    <MemoryRouter initialEntries={[`/documents/${initialId}`]}>
      <AuthProvider>
        <Harness />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('DocumentDetailPage', () => {
  beforeEach(() => {
    mockedFetchCurrentUser.mockResolvedValue(memberUser);
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListPeople.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
  });

  afterEach(() => {
    vi.resetAllMocks();
    clearToken();
  });

  it('shows a loading state, then the document and its versions', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/DOC-0001/)).toBeInTheDocument();
    });
    expect(screen.getByText('report.pdf')).toBeInTheDocument();
  });

  it('loads under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    setToken('a.jwt.token');

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/documents/d1']}>
          <AuthProvider>
            <Routes>
              <Route path="/documents/:id" element={<DocumentDetailPage />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByText(/DOC-0001/)).toBeInTheDocument();
    });
  });

  it('shows an error message when loading fails', async () => {
    mockedGetDocument.mockRejectedValue(new Error('network error'));
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load this document/i);
  });

  it('shows an empty state when there are no versions yet', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    renderPage();

    expect(await screen.findByText(/no versions uploaded yet/i)).toBeInTheDocument();
  });

  it('uploads a new version and refreshes', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 200,
      offset: 0,
    });
    mockedUploadDocumentVersion.mockResolvedValue(draftVersion);
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(mockedListDocumentVersions).toHaveBeenCalledTimes(1);
    });

    const file = new File(['%PDF-1.7'], 'report.pdf', { type: 'application/pdf' });
    const input = screen.getByLabelText(/^file$/i);
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /^upload version$/i }));

    await waitFor(() => {
      expect(mockedUploadDocumentVersion).toHaveBeenCalledWith('d1', file, undefined);
    });
    await waitFor(() => {
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });
  });

  it('submits a draft version for approval', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedSubmitVersionForApproval.mockResolvedValue({ ...draftVersion, status: 'in_review' });
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [{ ...draftVersion, status: 'in_review' }],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /submit for approval/i }));

    await waitFor(() => {
      expect(mockedSubmitVersionForApproval).toHaveBeenCalledWith('d1', 'v1');
    });
  });

  it('shows approve/reject controls only for an admin viewing an in_review version', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [inReviewVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it('an admin can approve an in_review version', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [inReviewVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedApproveVersion.mockResolvedValue({ ...inReviewVersion, status: 'approved' });
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [{ ...inReviewVersion, status: 'approved' }],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^approve$/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^approve$/i }));

    await waitFor(() => {
      expect(mockedApproveVersion).toHaveBeenCalledWith('d1', 'v2', undefined);
    });
  });

  it('requires a comment before an admin can reject a version', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [inReviewVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^reject$/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^reject$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/comment explaining the rejection/i);
    expect(mockedRejectVersion).not.toHaveBeenCalled();
  });

  it('an admin can reject a version with a comment', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [inReviewVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedRejectVersion.mockResolvedValue({ ...inReviewVersion, status: 'rejected' });
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [{ ...inReviewVersion, status: 'rejected' }],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^reject$/i })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/review comments/i), {
      target: { value: 'Not ready yet' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^reject$/i }));

    await waitFor(() => {
      expect(mockedRejectVersion).toHaveBeenCalledWith('d1', 'v2', 'Not ready yet');
    });
  });

  it('acknowledges a version', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedAcknowledgeVersion.mockResolvedValue({
      id: 'ack1',
      document_version_id: 'v1',
      acknowledged_by_id: 'u1',
      acknowledged_at: '2026-07-26T00:00:00Z',
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^acknowledge$/i }));

    await waitFor(() => {
      expect(mockedAcknowledgeVersion).toHaveBeenCalledWith('d1', 'v1');
    });
  });

  it('shows who has acknowledged a version', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListVersionAcknowledgements.mockResolvedValue({
      items: [
        {
          id: 'ack1',
          document_version_id: 'v1',
          acknowledged_by_id: 'u1',
          acknowledged_at: '2026-07-26T00:00:00Z',
        },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /who acknowledged/i }));

    await waitFor(() => {
      expect(mockedListVersionAcknowledgements).toHaveBeenCalledWith('d1', 'v1', {
        limit: 200,
        offset: 0,
      });
    });
    expect(await screen.findByText(/u1/)).toBeInTheDocument();
  });

  it('downloads a version', async () => {
    // jsdom doesn't implement real `<a>` navigation, so the browser-download
    // trigger pattern's `.click()` needs a local stub here -- scoped to this test
    // rather than a global one in test/setup.ts, per the "avoid a global anchor
    // click mock" review finding.
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedDownloadDocumentVersion.mockResolvedValue(new Blob(['%PDF-1.7']));

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^download report\.pdf$/i }));

    await waitFor(() => {
      expect(mockedDownloadDocumentVersion).toHaveBeenCalledWith('d1', 'v1');
    });
    clickSpy.mockRestore();
  });

  it('previews a previewable version inline', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedPreviewDocumentVersion.mockResolvedValue(
      new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    );

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() => {
      expect(mockedPreviewDocumentVersion).toHaveBeenCalledWith('d1', 'v1');
    });
    expect(await screen.findByTitle(/preview of report\.pdf/i)).toBeInTheDocument();
  });

  it('shows "Download to view" for a non-previewable content type instead of a preview button', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({
      items: [{ ...draftVersion, content_type: 'text/csv', original_filename: 'data.csv' }],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('data.csv')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /^preview$/i })).not.toBeInTheDocument();
    expect(screen.getByText(/preview not available/i)).toBeInTheDocument();
  });

  it('allows an admin to retire the document', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    renderPage();

    expect(await screen.findByRole('button', { name: /retire document/i })).toBeInTheDocument();
  });

  it('does not show a retire button for a non-admin', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(mockedGetDocument).toHaveBeenCalled();
    });

    expect(screen.queryByRole('button', { name: /retire document/i })).not.toBeInTheDocument();
  });

  it('an admin confirms before retiring, and the retire actually happens', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValueOnce(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedRetireDocument.mockResolvedValue({ ...documentFixture, status: 'obsolete' });
    mockedGetDocument.mockResolvedValueOnce({ ...documentFixture, status: 'obsolete' });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderPage();
    const retireButton = await screen.findByRole('button', { name: /retire document/i });
    fireEvent.click(retireButton);

    await waitFor(() => {
      expect(mockedRetireDocument).toHaveBeenCalledWith('d1');
    });
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('does not retire when the confirmation is declined', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    renderPage();
    const retireButton = await screen.findByRole('button', { name: /retire document/i });
    fireEvent.click(retireButton);

    await Promise.resolve();
    expect(mockedRetireDocument).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('disables the retire button while a retire is in flight', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    const retireDeferred = deferred<DocumentRecord>();
    mockedRetireDocument.mockReturnValue(retireDeferred.promise);
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderPage();
    const retireButton = await screen.findByRole('button', { name: /retire document/i });
    fireEvent.click(retireButton);

    await waitFor(() => {
      expect(retireButton).toBeDisabled();
    });
    retireDeferred.resolve({ ...documentFixture, status: 'obsolete' });
  });

  it('an admin can soft-delete the document after confirming, then is redirected', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedDeleteDocument.mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderPage();
    const deleteButton = await screen.findByRole('button', { name: /delete document/i });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockedDeleteDocument).toHaveBeenCalledWith('d1');
    });
  });

  it('does not delete the document when the confirmation is declined', async () => {
    mockedFetchCurrentUser.mockResolvedValue(adminUser);
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    renderPage();
    const deleteButton = await screen.findByRole('button', { name: /delete document/i });
    fireEvent.click(deleteButton);

    await Promise.resolve();
    expect(mockedDeleteDocument).not.toHaveBeenCalled();
  });

  it('does not show a delete button for a non-admin', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(mockedGetDocument).toHaveBeenCalled();
    });

    expect(screen.queryByRole('button', { name: /delete document/i })).not.toBeInTheDocument();
  });

  it('shows the category and owner names in the document header once loaded', async () => {
    mockedGetDocument.mockResolvedValue({
      ...documentFixture,
      category_id: 'c1',
      owner_id: 'p1',
    });
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListCategories.mockResolvedValue({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListPeople.mockResolvedValue({ items: [ownerPerson], total: 1, limit: 200, offset: 0 });

    renderPage();

    expect(await screen.findByText(/Category:\s*Quality/i)).toBeInTheDocument();
    expect(await screen.findByText(/jane doe/i)).toBeInTheDocument();
  });

  it('edits the document title, category, owner, and tags', async () => {
    mockedGetDocument.mockResolvedValueOnce(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListCategories.mockResolvedValue({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListPeople.mockResolvedValue({ items: [ownerPerson], total: 1, limit: 200, offset: 0 });
    mockedUpdateDocument.mockResolvedValue({
      ...documentFixture,
      title: 'Quality Manual v2',
      category_id: 'c1',
      owner_id: 'p1',
    });
    mockedGetDocument.mockResolvedValueOnce({
      ...documentFixture,
      title: 'Quality Manual v2',
      category_id: 'c1',
      owner_id: 'p1',
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/DOC-0001/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit details/i }));
    fireEvent.change(screen.getByLabelText(/^title$/i), {
      target: { value: 'Quality Manual v2' },
    });
    fireEvent.change(screen.getByLabelText(/^category$/i), { target: { value: 'c1' } });
    fireEvent.change(screen.getByLabelText(/^owner$/i), { target: { value: 'p1' } });
    fireEvent.click(screen.getByRole('button', { name: /^save changes$/i }));

    await waitFor(() => {
      expect(mockedUpdateDocument).toHaveBeenCalledWith('d1', {
        title: 'Quality Manual v2',
        category_id: 'c1',
        owner_id: 'p1',
        tag_ids: [],
      });
    });
    expect(await screen.findByText(/Quality Manual v2/)).toBeInTheDocument();
  });

  it('shows the edit-details button to a non-admin (metadata editing is any active user)', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/DOC-0001/)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /edit details/i })).toBeInTheDocument();
  });

  it('clears the file input after a successful upload', async () => {
    mockedGetDocument.mockResolvedValue(documentFixture);
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 200,
      offset: 0,
    });
    mockedUploadDocumentVersion.mockResolvedValue(draftVersion);
    mockedListDocumentVersions.mockResolvedValueOnce({
      items: [draftVersion],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(mockedListDocumentVersions).toHaveBeenCalledTimes(1);
    });

    const file = new File(['%PDF-1.7'], 'report.pdf', { type: 'application/pdf' });
    const input = screen.getByLabelText(/^file$/i);
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /^upload version$/i }));

    await waitFor(() => {
      expect(mockedUploadDocumentVersion).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });

  describe('out-of-order responses', () => {
    it('does not let a stale document load (from a previous route id) clobber the current one', async () => {
      const firstLoad = deferred<typeof documentFixture>();
      const firstVersions = deferred<{ items: []; total: number; limit: number; offset: number }>();
      mockedGetDocument.mockImplementation((docId: string) =>
        docId === 'd1'
          ? firstLoad.promise
          : Promise.resolve({
              ...documentFixture,
              id: 'd2',
              number: 'DOC-0002',
              title: 'Second Doc',
            }),
      );
      mockedListDocumentVersions.mockImplementation((docId: string) =>
        docId === 'd1'
          ? firstVersions.promise
          : Promise.resolve({ items: [], total: 0, limit: 200, offset: 0 }),
      );

      renderWithNavigationHarness('d1');

      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));

      await waitFor(() => {
        expect(screen.getByText(/DOC-0002/)).toBeInTheDocument();
      });

      firstLoad.resolve(documentFixture);
      firstVersions.resolve({ items: [], total: 0, limit: 200, offset: 0 });
      await Promise.resolve();
      await Promise.resolve();

      expect(screen.getByText(/DOC-0002/)).toBeInTheDocument();
      expect(screen.queryByText(/DOC-0001/)).not.toBeInTheDocument();
    });

    it('does not let a stale acknowledgements response (for a previously expanded version) overwrite the current one', async () => {
      const secondVersion = { ...draftVersion, id: 'v2', original_filename: 'policy.pdf' };
      mockedGetDocument.mockResolvedValue(documentFixture);
      mockedListDocumentVersions.mockResolvedValue({
        items: [draftVersion, secondVersion],
        total: 2,
        limit: 200,
        offset: 0,
      });
      const v1Ack = deferred<{
        items: {
          id: string;
          document_version_id: string;
          acknowledged_by_id: string;
          acknowledged_at: string;
        }[];
        total: number;
        limit: number;
        offset: number;
      }>();
      mockedListVersionAcknowledgements.mockImplementation((_docId: string, versionId: string) =>
        versionId === 'v1'
          ? v1Ack.promise
          : Promise.resolve({
              items: [
                {
                  id: 'ack2',
                  document_version_id: 'v2',
                  acknowledged_by_id: 'u2-fresh',
                  acknowledged_at: '2026-07-26T00:00:00Z',
                },
              ],
              total: 1,
              limit: 200,
              offset: 0,
            }),
      );

      renderPage();
      await waitFor(() => {
        expect(screen.getByText('policy.pdf')).toBeInTheDocument();
      });

      const whoAckButtons = screen.getAllByRole('button', { name: /who acknowledged/i });
      const [firstAckButton, secondAckButton] = whoAckButtons;
      if (!firstAckButton || !secondAckButton) {
        throw new Error('Expected two "who acknowledged" buttons, one per version.');
      }
      fireEvent.click(firstAckButton);
      fireEvent.click(secondAckButton);

      await waitFor(() => {
        expect(screen.getByText(/u2-fresh/)).toBeInTheDocument();
      });

      v1Ack.resolve({
        items: [
          {
            id: 'ack1',
            document_version_id: 'v1',
            acknowledged_by_id: 'u1-stale',
            acknowledged_at: '2026-07-26T00:00:00Z',
          },
        ],
        total: 1,
        limit: 200,
        offset: 0,
      });
      await Promise.resolve();
      await Promise.resolve();

      expect(screen.getByText(/u2-fresh/)).toBeInTheDocument();
      expect(screen.queryByText(/u1-stale/)).not.toBeInTheDocument();
    });

    it('does not let a stale preview response (for a previously selected version) render over the current one', async () => {
      const secondVersion = { ...draftVersion, id: 'v2', original_filename: 'policy.pdf' };
      mockedGetDocument.mockResolvedValue(documentFixture);
      mockedListDocumentVersions.mockResolvedValue({
        items: [draftVersion, secondVersion],
        total: 2,
        limit: 200,
        offset: 0,
      });
      const v1Preview = deferred<Blob>();
      mockedPreviewDocumentVersion.mockImplementation((_docId: string, versionId: string) =>
        versionId === 'v1'
          ? v1Preview.promise
          : Promise.resolve(new Blob(['%PDF-1.7'], { type: 'application/pdf' })),
      );

      renderPage();
      await waitFor(() => {
        expect(screen.getByText('policy.pdf')).toBeInTheDocument();
      });

      const previewButtons = screen.getAllByRole('button', { name: /^preview$/i });
      const [firstPreviewButton, secondPreviewButton] = previewButtons;
      if (!firstPreviewButton || !secondPreviewButton) {
        throw new Error('Expected two "Preview" buttons, one per version.');
      }
      fireEvent.click(firstPreviewButton);
      fireEvent.click(secondPreviewButton);

      await waitFor(() => {
        expect(screen.getByTitle(/preview of policy\.pdf/i)).toBeInTheDocument();
      });

      v1Preview.resolve(new Blob(['%PDF-1.7'], { type: 'application/pdf' }));
      await Promise.resolve();
      await Promise.resolve();

      expect(screen.getByTitle(/preview of policy\.pdf/i)).toBeInTheDocument();
      expect(screen.queryByTitle(/preview of report\.pdf/i)).not.toBeInTheDocument();
    });
  });

  describe('route id changes (component instance reused across navigation)', () => {
    /** d2's only version deliberately reuses id `'v1'` (with a different filename) --
     * this is what makes the preview/ack assertions below meaningful: if
     * `previewVersionId`/`expandedAckVersionId` were *not* reset on navigation, that
     * leftover state would still match d2's version by id and auto-render d1's
     * stale preview/acknowledgements for d2 *without any click*, exactly as if the
     * two states had never been separated. A d2 with no versions at all would make
     * these assertions pass trivially (the version row just wouldn't render),
     * proving nothing about whether the state was actually reset. */
    function mockD1ToD2Navigation(): void {
      mockedGetDocument.mockImplementation((docId: string) =>
        Promise.resolve(
          docId === 'd1'
            ? documentFixture
            : { ...documentFixture, id: 'd2', number: 'DOC-0002', title: 'Second Doc' },
        ),
      );
      mockedListDocumentVersions.mockImplementation((docId: string) =>
        Promise.resolve(
          docId === 'd1'
            ? { items: [draftVersion], total: 1, limit: 200, offset: 0 }
            : {
                items: [{ ...draftVersion, original_filename: 'other.pdf' }],
                total: 1,
                limit: 200,
                offset: 0,
              },
        ),
      );
    }

    it('clears an open preview from the previous document when navigating to a new one', async () => {
      mockD1ToD2Navigation();
      mockedPreviewDocumentVersion.mockResolvedValue(
        new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
      );

      renderWithNavigationHarness('d1');
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^preview$/i }));
      expect(await screen.findByTitle(/preview of report\.pdf/i)).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));

      await waitFor(() => {
        expect(screen.getByText('other.pdf')).toBeInTheDocument();
      });
      // Not just "preview of report.pdf" (which is trivially gone since d1's version
      // row itself is gone) -- also check d2's own, same-id version isn't showing an
      // auto-rendered stale preview it was never asked for.
      expect(screen.queryByTitle(/preview of other\.pdf/i)).not.toBeInTheDocument();
      expect(mockedPreviewDocumentVersion).toHaveBeenCalledTimes(1);
    });

    it('does not let a stale preview response from a previous document apply after navigating away', async () => {
      mockD1ToD2Navigation();
      const v1Preview = deferred<Blob>();
      mockedPreviewDocumentVersion.mockReturnValue(v1Preview.promise);

      renderWithNavigationHarness('d1');
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^preview$/i }));
      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));

      await waitFor(() => {
        expect(screen.getByText('other.pdf')).toBeInTheDocument();
      });

      v1Preview.resolve(new Blob(['%PDF-1.7'], { type: 'application/pdf' }));
      await Promise.resolve();
      await Promise.resolve();

      expect(screen.queryByTitle(/preview of other\.pdf/i)).not.toBeInTheDocument();
    });

    it('does not trigger a stale download after navigating to another document', async () => {
      mockD1ToD2Navigation();
      const pendingDownload = deferred<Blob>();
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      mockedDownloadDocumentVersion.mockReturnValue(pendingDownload.promise);

      renderWithNavigationHarness('d1');
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^download report\.pdf$/i }));
      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));
      await waitFor(() => {
        expect(screen.getByText('other.pdf')).toBeInTheDocument();
      });

      pendingDownload.resolve(new Blob(['%PDF-1.7']));
      await Promise.resolve();
      await Promise.resolve();

      expect(clickSpy).not.toHaveBeenCalled();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      clickSpy.mockRestore();
    });

    it('does not let stale edit options from the previous document overwrite current options', async () => {
      mockD1ToD2Navigation();
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

      renderWithNavigationHarness('d1');
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));
      await waitFor(() => {
        expect(screen.getByText('other.pdf')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByRole('button', { name: /edit details/i }));
      expect(await screen.findByRole('option', { name: 'Quality' })).toBeInTheDocument();

      staleCategories.resolve({ items: [], total: 0, limit: 200, offset: 0 });
      await Promise.resolve();
      await Promise.resolve();

      expect(screen.getByRole('option', { name: 'Quality' })).toBeInTheDocument();
    });

    it('clears an expanded acknowledgements panel from the previous document when navigating to a new one', async () => {
      mockD1ToD2Navigation();
      mockedListVersionAcknowledgements.mockResolvedValue({
        items: [
          {
            id: 'ack1',
            document_version_id: 'v1',
            acknowledged_by_id: 'u1-stale',
            acknowledged_at: '2026-07-26T00:00:00Z',
          },
        ],
        total: 1,
        limit: 200,
        offset: 0,
      });

      renderWithNavigationHarness('d1');
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /who acknowledged/i }));
      expect(await screen.findByText(/u1-stale/)).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));

      await waitFor(() => {
        expect(screen.getByText('other.pdf')).toBeInTheDocument();
      });
      expect(screen.queryByText(/u1-stale/)).not.toBeInTheDocument();
      expect(mockedListVersionAcknowledgements).toHaveBeenCalledTimes(1);
    });

    it('clears an action error from the previous document when navigating to a new one', async () => {
      mockD1ToD2Navigation();
      mockedAcknowledgeVersion.mockRejectedValue(new Error('network error'));

      renderWithNavigationHarness('d1');
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^acknowledge$/i }));
      expect(await screen.findByRole('alert')).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));

      await waitFor(() => {
        expect(screen.getByText(/DOC-0002/)).toBeInTheDocument();
      });
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('closes an open "edit details" form from the previous document when navigating to a new one', async () => {
      mockD1ToD2Navigation();

      renderWithNavigationHarness('d1');
      await waitFor(() => {
        expect(screen.getByText(/DOC-0001/)).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /edit details/i }));
      expect(screen.getByRole('form', { name: /edit document details/i })).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /go to d2/i }));

      await waitFor(() => {
        expect(screen.getByText(/DOC-0002/)).toBeInTheDocument();
      });
      expect(
        screen.queryByRole('form', { name: /edit document details/i }),
      ).not.toBeInTheDocument();
    });
  });

  describe('preview hardening', () => {
    it('shows an error instead of rendering a preview whose content type does not match an expected previewable type', async () => {
      mockedGetDocument.mockResolvedValue(documentFixture);
      mockedListDocumentVersions.mockResolvedValue({
        items: [draftVersion],
        total: 1,
        limit: 200,
        offset: 0,
      });
      mockedPreviewDocumentVersion.mockResolvedValue(
        new Blob(['<html>unexpected</html>'], { type: 'text/html' }),
      );

      renderPage();
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^preview$/i }));

      expect(await screen.findByRole('alert')).toHaveTextContent(/unexpected content type/i);
      expect(screen.queryByTitle(/preview of report\.pdf/i)).not.toBeInTheDocument();
    });

    it('renders an image preview with an <img>, not an <iframe>', async () => {
      mockedGetDocument.mockResolvedValue(documentFixture);
      mockedListDocumentVersions.mockResolvedValue({
        items: [{ ...draftVersion, content_type: 'image/png', original_filename: 'photo.png' }],
        total: 1,
        limit: 200,
        offset: 0,
      });
      mockedPreviewDocumentVersion.mockResolvedValue(new Blob(['x'], { type: 'image/png' }));

      renderPage();
      await waitFor(() => {
        expect(screen.getByText('photo.png')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^preview$/i }));

      const image = await screen.findByAltText(/preview of photo\.png/i);
      expect(image.tagName).toBe('IMG');
    });

    it('sandboxes the iframe used to preview a PDF', async () => {
      mockedGetDocument.mockResolvedValue(documentFixture);
      mockedListDocumentVersions.mockResolvedValue({
        items: [draftVersion],
        total: 1,
        limit: 200,
        offset: 0,
      });
      mockedPreviewDocumentVersion.mockResolvedValue(
        new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
      );

      renderPage();
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^preview$/i }));

      const frame = await screen.findByTitle(/preview of report\.pdf/i);
      expect(frame).toHaveAttribute('sandbox');
    });
  });

  describe('download', () => {
    it('defers revoking the download object URL via a scheduled timer instead of doing it synchronously', async () => {
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      const setTimeoutSpy = vi.spyOn(window, 'setTimeout');
      mockedGetDocument.mockResolvedValue(documentFixture);
      mockedListDocumentVersions.mockResolvedValue({
        items: [draftVersion],
        total: 1,
        limit: 200,
        offset: 0,
      });
      mockedDownloadDocumentVersion.mockResolvedValue(new Blob(['%PDF-1.7']));

      renderPage();
      await waitFor(() => {
        expect(screen.getByText('report.pdf')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^download report\.pdf$/i }));

      await waitFor(() => {
        expect(mockedDownloadDocumentVersion).toHaveBeenCalled();
      });
      await waitFor(() => {
        // Revocation must be scheduled via a timer (deferred), not performed
        // immediately in the same tick as the click -- real browsers need time to
        // start consuming a `blob:` URL before it's safe to revoke. Matched on the
        // exact delay (not just "some" setTimeout call) since other library
        // internals (React, RTL) may also schedule unrelated timers.
        expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 30_000);
      });

      setTimeoutSpy.mockRestore();
      clickSpy.mockRestore();
    });
  });
});
