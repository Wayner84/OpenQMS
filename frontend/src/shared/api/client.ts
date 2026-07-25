/**
 * Shared typed fetch wrapper. Every module's API calls go through this instead of
 * calling `fetch` directly, per docs/CodingStandards.md#frontend-react-typescript.
 */

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

/**
 * GETs `path` against the configured API base URL and returns the parsed JSON body.
 * Throws {@link ApiError} (with the parsed body attached, when present) for non-2xx
 * responses, so callers that need a non-2xx body (e.g. a documented degraded-state
 * response) can recover it from `error.body`.
 */
export async function apiGet<T>(path: string): Promise<T> {
  const baseUrl = getBaseUrl();
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { Accept: 'application/json' },
  });
  const body = await parseJsonBody(response);
  if (!response.ok) {
    throw new ApiError(`GET ${path} failed with status ${response.status}`, response.status, body);
  }
  return body as T;
}
