import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import {
  createCertification,
  createPerformanceRecord,
  createSupplier,
  deleteCertification,
  deleteSupplier,
  getSupplier,
  listCertifications,
  listExpiringCertifications,
  listPerformanceRecords,
  listSuppliers,
  updateCertification,
  updateSupplier,
} from './api';

describe('suppliers api', () => {
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

  describe('listSuppliers', () => {
    it('requests the default page when called with no arguments', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listSuppliers();

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/suppliers');
    });

    it('encodes every filter as a query parameter', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 }), {
          status: 200,
        }),
      );

      await listSuppliers({
        approvalStatus: 'approved',
        riskRating: 'high',
        isPreferred: true,
        search: 'acme',
        limit: 20,
        offset: 0,
      });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        'http://localhost:8000/api/v1/suppliers?approval_status=approved&risk_rating=high&is_preferred=true&search=acme&limit=20&offset=0',
      );
    });
  });

  describe('getSupplier', () => {
    it('GETs the supplier by id', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 's1' }), { status: 200 }),
      );

      await getSupplier('s1');

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/suppliers/s1');
    });
  });

  describe('createSupplier', () => {
    it('POSTs the new-supplier payload', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 's1' }), { status: 201 }),
      );

      await createSupplier({
        company_id: 'c1',
        approval_status: 'pending',
        is_preferred: false,
      });

      const [url, init] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/suppliers');
      expect(init?.method).toBe('POST');
      expect(JSON.parse(init?.body as string)).toEqual({
        company_id: 'c1',
        approval_status: 'pending',
        is_preferred: false,
      });
    });
  });

  describe('updateSupplier', () => {
    it('PATCHes the supplier by id', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 's1' }), { status: 200 }),
      );

      await updateSupplier('s1', {
        company_id: 'c1',
        approval_status: 'approved',
        is_preferred: true,
      });

      const [url, init] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/suppliers/s1');
      expect(init?.method).toBe('PATCH');
    });
  });

  describe('deleteSupplier', () => {
    it('DELETEs the supplier by id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await deleteSupplier('s1');

      const [url, init] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/suppliers/s1');
      expect(init?.method).toBe('DELETE');
    });
  });

  describe('certifications', () => {
    it('lists, creates, updates, and deletes a certification', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );
      await listCertifications('s1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/suppliers/s1/certifications',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'cert1' }), { status: 201 }),
      );
      await createCertification('s1', { certification_type: 'ISO 9001' });
      expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe(
        'http://localhost:8000/api/v1/suppliers/s1/certifications',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'cert1' }), { status: 200 }),
      );
      await updateCertification('s1', 'cert1', { certification_type: 'AS9100' });
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe(
        'http://localhost:8000/api/v1/suppliers/s1/certifications/cert1',
      );

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      await deleteCertification('s1', 'cert1');
      expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe(
        'http://localhost:8000/api/v1/suppliers/s1/certifications/cert1',
      );
    });
  });

  describe('listExpiringCertifications', () => {
    it('encodes within_days as a query parameter', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listExpiringCertifications({ withinDays: 60 });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        'http://localhost:8000/api/v1/suppliers/certifications/expiring?within_days=60',
      );
    });
  });

  describe('performance records', () => {
    it('lists and creates a performance record', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );
      await listPerformanceRecords('s1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/suppliers/s1/performance',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'p1' }), { status: 201 }),
      );
      await createPerformanceRecord('s1', { period: '2026-Q3', score: '90.00' });
      expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe(
        'http://localhost:8000/api/v1/suppliers/s1/performance',
      );
    });
  });
});
