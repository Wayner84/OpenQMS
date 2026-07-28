import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import {
  acknowledgeVersion,
  approveVersion,
  compareVersions,
  createCategory,
  createDocument,
  createTag,
  deleteCategory,
  deleteTag,
  downloadDocumentVersion,
  listDocuments,
  listDocumentVersions,
  listVersionAcknowledgements,
  previewDocumentVersion,
  rejectVersion,
  retireDocument,
  submitVersionForApproval,
  uploadDocumentVersion,
} from './api';

describe('documents api', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubGlobal('fetch', vi.fn());
    setToken('a.jwt.token');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    clearToken();
  });

  describe('listDocuments', () => {
    it('requests the default page when called with no arguments', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listDocuments();

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents');
    });

    it('encodes all filters and pagination as query parameters', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 10, offset: 0 }), {
          status: 200,
        }),
      );

      await listDocuments({
        categoryId: 'cat1',
        status: 'approved',
        ownerId: 'p1',
        search: 'quality',
        tag: 'controlled',
        limit: 10,
        offset: 0,
      });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        'http://localhost:8000/api/v1/documents?category_id=cat1&status=approved&owner_id=p1&search=quality&tag=controlled&limit=10&offset=0',
      );
    });
  });

  describe('createDocument', () => {
    it('POSTs the new-document payload', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'd1' }), { status: 201 }),
      );

      await createDocument({ title: 'Quality Manual' });

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents');
      expect(options?.method).toBe('POST');
      expect(options?.body).toBe(JSON.stringify({ title: 'Quality Manual' }));
    });
  });

  describe('categories', () => {
    it('createCategory POSTs to /document-categories', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'c1' }), { status: 201 }),
      );

      await createCategory({ name: 'Quality' });

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/document-categories');
      expect(options?.method).toBe('POST');
    });

    it('deleteCategory DELETEs the given category id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await deleteCategory('c1');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/document-categories/c1');
      expect(options?.method).toBe('DELETE');
    });
  });

  describe('tags', () => {
    it('createTag POSTs to /document-tags', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 't1' }), { status: 201 }),
      );

      await createTag({ name: 'controlled' });

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/document-tags');
      expect(options?.method).toBe('POST');
    });

    it('deleteTag DELETEs the given tag id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await deleteTag('t1');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/document-tags/t1');
      expect(options?.method).toBe('DELETE');
    });
  });

  describe('listDocumentVersions', () => {
    it("requests the document's versions", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 200, offset: 0 }), {
          status: 200,
        }),
      );

      await listDocumentVersions('d1', { limit: 200 });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions?limit=200');
    });
  });

  describe('uploadDocumentVersion', () => {
    it('POSTs a FormData body with the file and change summary, without a Content-Type header', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'v1' }), { status: 201 }),
      );
      const file = new File(['%PDF-1.7'], 'report.pdf', { type: 'application/pdf' });

      await uploadDocumentVersion('d1', file, 'Initial draft');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions');
      expect(options?.method).toBe('POST');
      expect(options?.body).toBeInstanceOf(FormData);
      const body = options?.body as FormData;
      expect(body.get('file')).toBe(file);
      expect(body.get('change_summary')).toBe('Initial draft');
      expect(new Headers(options?.headers).has('Content-Type')).toBe(false);
    });

    it('omits change_summary from the form when not provided', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'v1' }), { status: 201 }),
      );
      const file = new File(['hello'], 'notes.txt', { type: 'text/plain' });

      await uploadDocumentVersion('d1', file);

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      const body = options?.body as FormData;
      expect(body.get('change_summary')).toBeNull();
    });
  });

  describe('downloadDocumentVersion / previewDocumentVersion', () => {
    it('downloadDocumentVersion GETs the download URL and returns a Blob', async () => {
      // A plain string body with an explicit header, not `new Response(new Blob(...))`:
      // see the equivalent note in client.test.ts's `apiGetBlob` test -- jsdom's
      // `Blob` isn't recognised by Node's own `Response`, a jsdom/Node interop
      // artifact of this test environment, not real browser behaviour.
      vi.mocked(fetch).mockResolvedValue(
        new Response('%PDF-1.7', { status: 200, headers: { 'Content-Type': 'application/pdf' } }),
      );

      const result = await downloadDocumentVersion('d1', 'v1');

      expect(result.size).toBe(8);
      expect(result.type).toBe('application/pdf');
      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions/v1/download');
    });

    it('previewDocumentVersion GETs the preview URL and returns a Blob', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response('%PDF-1.7', { status: 200, headers: { 'Content-Type': 'application/pdf' } }),
      );

      const result = await previewDocumentVersion('d1', 'v1');

      expect(result.size).toBe(8);
      expect(result.type).toBe('application/pdf');
      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions/v1/preview');
    });
  });

  describe('workflow', () => {
    it('submitVersionForApproval POSTs to submit-for-approval', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await submitVersionForApproval('d1', 'v1');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions/v1/submit-for-approval');
      expect(options?.method).toBe('POST');
    });

    it('approveVersion POSTs comments to approve', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await approveVersion('d1', 'v1', 'Looks good');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions/v1/approve');
      expect(options?.body).toBe(JSON.stringify({ comments: 'Looks good' }));
    });

    it('rejectVersion POSTs the required comments to reject', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await rejectVersion('d1', 'v1', 'Not ready');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions/v1/reject');
      expect(options?.body).toBe(JSON.stringify({ comments: 'Not ready' }));
    });

    it('retireDocument POSTs to /obsolete', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await retireDocument('d1');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/obsolete');
      expect(options?.method).toBe('POST');
    });
  });

  describe('acknowledgements', () => {
    it('acknowledgeVersion POSTs to acknowledge', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await acknowledgeVersion('d1', 'v1');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions/v1/acknowledge');
      expect(options?.method).toBe('POST');
    });

    it('listVersionAcknowledgements GETs the acknowledgements list', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 200, offset: 0 }), {
          status: 200,
        }),
      );

      await listVersionAcknowledgements('d1', 'v1', { limit: 200 });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        'http://localhost:8000/api/v1/documents/d1/versions/v1/acknowledgements?limit=200',
      );
    });
  });

  describe('compareVersions', () => {
    it('GETs the compare endpoint for the two given versions', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(
          JSON.stringify({
            version_a: {},
            version_b: {},
            checksum_changed: true,
            text_diff: null,
          }),
          { status: 200 },
        ),
      );

      await compareVersions('d1', 'va', 'vb');

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/d1/versions/va/compare/vb');
    });
  });
});
