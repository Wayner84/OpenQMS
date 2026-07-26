/**
 * Shared typed fetch wrapper. Every module's API calls go through this instead of
 * calling `fetch` directly, per docs/CodingStandards.md#frontend-react-typescript.
 * Attaches the base URL, JSON headers, and (once a token is stored) the bearer
 * token to every request.
 */

import { emitUnauthorized } from '../auth/sessionEvents';
import { getToken } from '../auth/tokenStore';

/** Thrown for any non-2xx response; `body` carries the parsed JSON if the response had one. */
export class ApiError extends Error {
  readonly status?: number;
  readonly body?: unknown;

  constructor(message: string, status?: number, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';

function getBaseUrl(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!baseUrl) {
    throw new ApiError('VITE_API_BASE_URL is not configured');
  }
  return baseUrl;
}

async function parseJsonBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

interface RequestOptions {
  /**
   * Skips attaching a stored bearer token to this request. Used for
   * `/auth/login`: it's a public endpoint, and attaching a stale-but-still-valid
   * token would make a plain "wrong password" `401` indistinguishable from a
   * revoked session, wrongly clearing a still-good token via `emitUnauthorized`.
   */
  skipAuth?: boolean;
}

async function request<T>(
  path: string,
  method: HttpMethod,
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const baseUrl = getBaseUrl();
  const headers = new Headers({ Accept: 'application/json' });
  if (body !== undefined) {
    headers.set('Content-Type', 'application/json');
  }
  const token = options?.skipAuth ? null : getToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const parsedBody = await parseJsonBody(response);
  if (!response.ok) {
    if (response.status === 401 && token) {
      // A request that carried a token was rejected: the session expired, was
      // revoked (logout elsewhere), or the user was deactivated since the last
      // check. A 401 with no token attached (e.g. bad login credentials) is a
      // normal, expected rejection the caller already handles inline.
      emitUnauthorized();
    }
    throw new ApiError(
      `${method} ${path} failed with status ${response.status}`,
      response.status,
      parsedBody,
    );
  }
  return parsedBody as T;
}

/**
 * GETs `path` against the configured API base URL and returns the parsed JSON body.
 * Throws {@link ApiError} (with the parsed body attached, when present) for non-2xx
 * responses, so callers that need a non-2xx body (e.g. a documented degraded-state
 * response) can recover it from `error.body`.
 */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, 'GET');
}

/** POSTs `body` as JSON to `path`. See {@link apiGet} for the error contract. */
export function apiPost<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  return request<T>(path, 'POST', body, options);
}

/** PATCHes `body` as JSON to `path`. See {@link apiGet} for the error contract. */
export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, 'PATCH', body);
}

/** DELETEs `path`. See {@link apiGet} for the error contract. */
export function apiDelete<T = void>(path: string): Promise<T> {
  return request<T>(path, 'DELETE');
}

/**
 * Extracts the server's human-readable `detail` message (per
 * docs/API.md#error-format) from a caught error, or `null` if `error` isn't an
 * {@link ApiError} with a string `detail` in its body. Lets callers show the
 * server's own explanation (e.g. a 409 guard message) instead of re-deriving it.
 */
export function getErrorDetail(error: unknown): string | null {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return null;
  }
  const detail = (error.body as Record<string, unknown>).detail;
  return typeof detail === 'string' ? detail : null;
}
