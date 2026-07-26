import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import {
  createCompany,
  createPerson,
  deleteCompany,
  deletePerson,
  listCompanies,
  listCompanyPeople,
  listPeople,
  updateCompany,
  updatePerson,
} from './api';

describe('people api', () => {
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

  describe('listCompanies', () => {
    it('requests the default page when called with no arguments', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listCompanies();

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/companies');
    });

    it('encodes limit and offset as query parameters', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 10, offset: 20 }), {
          status: 200,
        }),
      );

      await listCompanies({ limit: 10, offset: 20 });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/companies?limit=10&offset=20');
    });
  });

  describe('createCompany', () => {
    it('POSTs the new-company payload', async () => {
      const created = {
        id: 'c1',
        organisation_id: 'o1',
        name: 'Acme Ltd',
        type: 'customer',
        address: null,
        phone: null,
        general_email: null,
        notes: null,
        created_by_id: 'u1',
        updated_by_id: 'u1',
      };
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

      const result = await createCompany({ name: 'Acme Ltd', type: 'customer' });

      expect(result).toEqual(created);
      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/companies');
      expect(options?.method).toBe('POST');
    });
  });

  describe('updateCompany', () => {
    it('PATCHes the given company id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await updateCompany('c1', { name: 'New Name', type: 'supplier' });

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/companies/c1');
      expect(options?.method).toBe('PATCH');
    });
  });

  describe('deleteCompany', () => {
    it('DELETEs the given company id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await deleteCompany('c1');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/companies/c1');
      expect(options?.method).toBe('DELETE');
    });
  });

  describe('listCompanyPeople', () => {
    it("requests the company's contacts", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listCompanyPeople('c1');

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/companies/c1/people');
    });
  });

  describe('listPeople', () => {
    it('requests the default page when called with no arguments', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listPeople();

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/people');
    });

    it('encodes all filters and pagination as query parameters', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 10, offset: 0 }), {
          status: 200,
        }),
      );

      await listPeople({
        companyId: 'c1',
        isEmployee: false,
        department: 'Sales',
        search: 'ada',
        limit: 10,
        offset: 0,
      });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        'http://localhost:8000/api/v1/people?company_id=c1&is_employee=false&department=Sales&search=ada&limit=10&offset=0',
      );
    });
  });

  describe('createPerson', () => {
    it('POSTs the new-person payload', async () => {
      const created = {
        id: 'p1',
        organisation_id: 'o1',
        company_id: null,
        first_name: 'Ada',
        last_name: 'Lovelace',
        email: null,
        phone: null,
        role: null,
        department: null,
        notes: null,
        is_employee: true,
        created_by_id: 'u1',
        updated_by_id: 'u1',
      };
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

      const result = await createPerson({
        first_name: 'Ada',
        last_name: 'Lovelace',
        is_employee: true,
      });

      expect(result).toEqual(created);
      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/people');
      expect(options?.method).toBe('POST');
    });
  });

  describe('updatePerson', () => {
    it('PATCHes the given person id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await updatePerson('p1', {
        first_name: 'Ada',
        last_name: 'Lovelace',
        is_employee: true,
      });

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/people/p1');
      expect(options?.method).toBe('PATCH');
    });
  });

  describe('deletePerson', () => {
    it('DELETEs the given person id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await deletePerson('p1');

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/people/p1');
      expect(options?.method).toBe('DELETE');
    });
  });
});
