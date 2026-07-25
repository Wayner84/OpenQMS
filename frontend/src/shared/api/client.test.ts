import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiGet } from './client';

describe('apiGet', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('requests the given path against the configured base URL and returns the parsed JSON body', async () => {
    const body = { status: 'ok' };
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));

    const result = await apiGet<typeof body>('/api/v1/health');

    expect(result).toEqual(body);
    expect(fetch).toHaveBeenCalledOnce();
    const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
    expect(url).toBe('http://localhost:8000/api/v1/health');
    expect(new Headers(options?.headers).get('Accept')).toBe('application/json');
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
});
