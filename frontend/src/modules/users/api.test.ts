import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import { createUser, listUsers, updateUser } from './api';

describe('users api', () => {
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

  describe('listUsers', () => {
    it('requests the default page when called with no arguments', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listUsers();

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/users');
    });

    it('encodes limit and offset as query parameters', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 10, offset: 20 }), {
          status: 200,
        }),
      );

      await listUsers({ limit: 10, offset: 20 });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/users?limit=10&offset=20');
    });
  });

  describe('createUser', () => {
    it('POSTs the new-user payload', async () => {
      const created = {
        id: 'u2',
        organisation_id: 'o1',
        email: 'new@example.com',
        full_name: 'New User',
        role: 'member',
        is_active: true,
      };
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

      const result = await createUser({
        email: 'new@example.com',
        full_name: 'New User',
        password: 'secret123',
        role: 'member',
      });

      expect(result).toEqual(created);
      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/users');
      expect(options?.method).toBe('POST');
    });
  });

  describe('updateUser', () => {
    it('PATCHes the given user id', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await updateUser('u2', { is_active: false });

      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/users/u2');
      expect(options?.method).toBe('PATCH');
      expect(options?.body).toBe(JSON.stringify({ is_active: false }));
    });
  });
});
