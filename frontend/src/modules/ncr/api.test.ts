import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import {
  createAction,
  createAttachment,
  createNcr,
  deleteAttachment,
  deleteNcr,
  exportNcr,
  getInvestigationTool,
  getNcr,
  listActions,
  listAttachments,
  listNcrs,
  listStatusHistory,
  transitionNcr,
  updateAction,
  updateNcr,
  upsertInvestigationTool,
} from './api';

describe('ncr api', () => {
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

  describe('listNcrs', () => {
    it('requests the default page when called with no arguments', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listNcrs();

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/ncr');
    });

    it('encodes every filter as a query parameter', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 }), {
          status: 200,
        }),
      );

      await listNcrs({
        type: 'internal',
        status: 'open',
        productId: 'pr1',
        supplierId: 's1',
        raisedById: 'p1',
        search: 'widget',
        limit: 20,
        offset: 0,
      });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        'http://localhost:8000/api/v1/ncr?type=internal&status=open&product_id=pr1&supplier_id=s1&raised_by_id=p1&search=widget&limit=20&offset=0',
      );
    });
  });

  describe('NCR CRUD and workflow', () => {
    it('gets, creates, updates, deletes, and transitions an NCR', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'n1' }), { status: 200 }),
      );
      await getNcr('n1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe('http://localhost:8000/api/v1/ncr/n1');

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'n1' }), { status: 201 }),
      );
      await createNcr({
        type: 'internal',
        raised_by_id: 'p1',
        description: 'A widget was out of spec',
      });
      expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe('http://localhost:8000/api/v1/ncr');

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'n1' }), { status: 200 }),
      );
      await updateNcr('n1', {
        type: 'internal',
        raised_by_id: 'p1',
        description: 'Updated description',
      });
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe('http://localhost:8000/api/v1/ncr/n1');

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      await deleteNcr('n1');
      expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe('http://localhost:8000/api/v1/ncr/n1');

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'n1', status: 'investigate' }), { status: 200 }),
      );
      await transitionNcr('n1', { to_status: 'investigate' });
      const [url, init] = vi.mocked(fetch).mock.calls[4] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/ncr/n1/transition');
      expect(JSON.parse(init?.body as string)).toEqual({ to_status: 'investigate' });
    });
  });

  describe('listStatusHistory', () => {
    it('requests the status-history endpoint', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listStatusHistory('n1');

      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/n1/status-history',
      );
    });
  });

  describe('exportNcr', () => {
    it('requests the export endpoint and returns a Blob', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response('%PDF-1.7', { status: 200, headers: { 'Content-Type': 'application/pdf' } }),
      );

      const result = await exportNcr('n1');

      expect(result.type).toBe('application/pdf');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/n1/export',
      );
    });
  });

  describe('actions', () => {
    it('lists, creates, and updates an action', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );
      await listActions('n1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/n1/actions',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'a1' }), { status: 201 }),
      );
      await createAction('n1', { description: 'Quarantine the batch' });
      expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/n1/actions',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'a1' }), { status: 200 }),
      );
      await updateAction('a1', { description: 'Quarantine the batch', status: 'complete' });
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/actions/a1',
      );
    });
  });

  describe('investigation tools', () => {
    it('gets and upserts a tool', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ ncr_id: 'n1', tool_type: 'five_why', data: {} }), {
          status: 200,
        }),
      );
      await getInvestigationTool('n1', 'five_why');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/n1/tools/five_why',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ ncr_id: 'n1', tool_type: 'five_why', data: {} }), {
          status: 200,
        }),
      );
      await upsertInvestigationTool('n1', 'five_why', { why_1: 'The seal failed' });
      const [url, init] = vi.mocked(fetch).mock.calls[1] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/ncr/n1/tools/five_why');
      expect(init?.method).toBe('PUT');
      expect(JSON.parse(init?.body as string)).toEqual({ data: { why_1: 'The seal failed' } });
    });
  });

  describe('attachments', () => {
    it('lists, creates, and deletes an attachment', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );
      await listAttachments('n1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/n1/attachments',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'att1' }), { status: 201 }),
      );
      await createAttachment('n1', { document_id: 'd1', description: 'Defect photo' });
      const [url, init] = vi.mocked(fetch).mock.calls[1] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/ncr/n1/attachments');
      expect(JSON.parse(init?.body as string)).toEqual({
        document_id: 'd1',
        description: 'Defect photo',
      });

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      await deleteAttachment('n1', 'att1');
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe(
        'http://localhost:8000/api/v1/ncr/n1/attachments/att1',
      );
    });
  });
});
