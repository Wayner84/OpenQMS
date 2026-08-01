import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { onUnauthorized } from '../auth/sessionEvents';
import { clearToken, setToken } from '../auth/tokenStore';
import {
  ApiError,
  apiDelete,
  apiGet,
  apiGetBlob,
  apiPatch,
  apiPost,
  apiPostForm,
  apiPut,
  getErrorDetail,
} from './client';

describe('api client', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    clearToken();
  });

  describe('apiGet', () => {
    it('requests the given path against the configured base URL and returns the parsed JSON body', async () => {
      const body = { status: 'ok' };
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));

      const result = await apiGet<typeof body>('/api/v1/health');

      expect(result).toEqual(body);
      expect(fetch).toHaveBeenCalledOnce();
      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/health');
      expect(options?.method).toBe('GET');
      expect(new Headers(options?.headers).get('Accept')).toBe('application/json');
      expect(new Headers(options?.headers).has('Authorization')).toBe(false);
    });

    it('rejects with an ApiError carrying the status and parsed body when the response is not ok', async () => {
      const body = { status: 'not_ready', database: 'error' };
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(body), { status: 503 }));

      await expect(apiGet('/api/v1/health/ready')).rejects.toMatchObject({
        name: 'ApiError',
        status: 503,
        body,
      });
    });

    it('attaches an Authorization bearer header when a token is stored', async () => {
      setToken('a.jwt.token');
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await apiGet('/api/v1/auth/me');

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(new Headers(options?.headers).get('Authorization')).toBe('Bearer a.jwt.token');
    });

    it('emits an unauthorized notification when an authenticated request is rejected with 401', async () => {
      setToken('expired.token');
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 401 }));
      const listener = vi.fn();
      const unsubscribe = onUnauthorized(listener);

      await expect(apiGet('/api/v1/people')).rejects.toMatchObject({ status: 401 });

      unsubscribe();
      expect(listener).toHaveBeenCalledOnce();
    });

    it('does not emit an unauthorized notification for a 401 with no token attached (e.g. bad login credentials)', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 401 }));
      const listener = vi.fn();
      const unsubscribe = onUnauthorized(listener);

      await expect(
        apiPost('/api/v1/auth/login', { email: 'a', password: 'b' }),
      ).rejects.toMatchObject({
        status: 401,
      });

      unsubscribe();
      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe('skipAuth', () => {
    it('omits a stored token and does not treat a 401 as session-invalidated, even if one is stored', async () => {
      setToken('still.valid.token');
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 401 }));
      const listener = vi.fn();
      const unsubscribe = onUnauthorized(listener);

      await expect(
        apiPost('/api/v1/auth/login', { email: 'a', password: 'wrong' }, { skipAuth: true }),
      ).rejects.toMatchObject({ status: 401 });

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(new Headers(options?.headers).has('Authorization')).toBe(false);
      unsubscribe();
      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe('apiPost', () => {
    it('sends a JSON body with a Content-Type header and returns the parsed response', async () => {
      const responseBody = { id: '1' };
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify(responseBody), { status: 201 }),
      );

      const result = await apiPost<typeof responseBody>('/api/v1/people', { first_name: 'Ada' });

      expect(result).toEqual(responseBody);
      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(options?.method).toBe('POST');
      expect(options?.body).toBe(JSON.stringify({ first_name: 'Ada' }));
      expect(new Headers(options?.headers).get('Content-Type')).toBe('application/json');
    });
  });

  describe('apiPatch', () => {
    it('sends a JSON body via PATCH', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await apiPatch('/api/v1/users/1', { is_active: false });

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(options?.method).toBe('PATCH');
      expect(options?.body).toBe(JSON.stringify({ is_active: false }));
    });
  });

  describe('apiPut', () => {
    it('sends a JSON body via PUT', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

      await apiPut('/api/v1/ncr/1/tools/five_why', { data: { why_1: 'It failed' } });

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(options?.method).toBe('PUT');
      expect(options?.body).toBe(JSON.stringify({ data: { why_1: 'It failed' } }));
      expect(new Headers(options?.headers).get('Content-Type')).toBe('application/json');
    });
  });

  describe('apiDelete', () => {
    it('sends a DELETE request with no body and tolerates an empty response', async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await expect(apiDelete('/api/v1/people/1')).resolves.toBeUndefined();

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(options?.method).toBe('DELETE');
      expect(options?.body).toBeUndefined();
    });
  });

  describe('apiPostForm', () => {
    it('sends a FormData body without setting a Content-Type header', async () => {
      const responseBody = { id: 'v1' };
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify(responseBody), { status: 201 }),
      );
      const formData = new FormData();
      formData.set('file', new Blob(['hello'], { type: 'text/plain' }), 'notes.txt');

      const result = await apiPostForm<typeof responseBody>(
        '/api/v1/documents/1/versions',
        formData,
      );

      expect(result).toEqual(responseBody);
      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(options?.method).toBe('POST');
      expect(options?.body).toBe(formData);
      expect(new Headers(options?.headers).has('Content-Type')).toBe(false);
      expect(new Headers(options?.headers).get('Accept')).toBe('application/json');
    });

    it('attaches an Authorization header when a token is stored', async () => {
      setToken('a.jwt.token');
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 201 }));

      await apiPostForm('/api/v1/documents/1/versions', new FormData());

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(new Headers(options?.headers).get('Authorization')).toBe('Bearer a.jwt.token');
    });

    it('rejects with an ApiError carrying the status and parsed body when the response is not ok', async () => {
      const body = { detail: 'File type not allowed' };
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(body), { status: 422 }));

      await expect(
        apiPostForm('/api/v1/documents/1/versions', new FormData()),
      ).rejects.toMatchObject({ name: 'ApiError', status: 422, body });
    });
  });

  describe('apiGetBlob', () => {
    it('requests the given path and returns the raw response body as a Blob', async () => {
      // A plain string body with an explicit header, not `new Response(new Blob(...))`:
      // jsdom's global `Blob` (what `new Blob()` constructs in this test environment)
      // isn't recognised as a Blob by Node's own `Response` implementation, which
      // silently stringifies it (`"[object Blob]"`) instead of using its bytes/type --
      // a jsdom/Node interop artifact of this test environment, not real browser
      // behaviour, where there is only one `Blob`/`Response` implementation.
      vi.mocked(fetch).mockResolvedValue(
        new Response('%PDF-1.7', { status: 200, headers: { 'Content-Type': 'application/pdf' } }),
      );

      const result = await apiGetBlob('/api/v1/documents/1/versions/2/download');

      expect(result.size).toBe(8);
      expect(result.type).toBe('application/pdf');
      const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/documents/1/versions/2/download');
      expect(options?.method).toBe('GET');
    });

    it('attaches an Authorization header when a token is stored', async () => {
      setToken('a.jwt.token');
      vi.mocked(fetch).mockResolvedValue(new Response(new Blob(['x']), { status: 200 }));

      await apiGetBlob('/api/v1/documents/1/versions/2/download');

      const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(new Headers(options?.headers).get('Authorization')).toBe('Bearer a.jwt.token');
    });

    it('rejects with an ApiError carrying the parsed JSON error body when the response is not ok', async () => {
      const body = { detail: 'Document version not found' };
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(body), { status: 404 }));

      await expect(apiGetBlob('/api/v1/documents/1/versions/2/download')).rejects.toMatchObject({
        name: 'ApiError',
        status: 404,
        body,
      });
    });

    it('emits an unauthorized notification when an authenticated request is rejected with 401', async () => {
      setToken('expired.token');
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 401 }));
      const listener = vi.fn();
      const unsubscribe = onUnauthorized(listener);

      await expect(apiGetBlob('/api/v1/documents/1/versions/2/download')).rejects.toMatchObject({
        status: 401,
      });

      unsubscribe();
      expect(listener).toHaveBeenCalledOnce();
    });
  });

  describe('getErrorDetail', () => {
    it('returns the server-provided detail message from an ApiError', () => {
      const error = new ApiError('failed', 409, { detail: 'Cannot deactivate the last admin' });

      expect(getErrorDetail(error)).toBe('Cannot deactivate the last admin');
    });

    it('returns null when the error is not an ApiError', () => {
      expect(getErrorDetail(new Error('network error'))).toBeNull();
    });

    it('returns null when the ApiError body has no string detail field', () => {
      expect(getErrorDetail(new ApiError('failed', 500, undefined))).toBeNull();
      expect(getErrorDetail(new ApiError('failed', 500, { detail: 42 }))).toBeNull();
    });
  });
});
