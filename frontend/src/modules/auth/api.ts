/** Typed client functions for the auth module, per docs/API.md#authentication. */

import { apiGet, apiPost } from '../../shared/api/client';
import type { LoginRequest, LoginResponse, User } from './types';

/**
 * POST /api/v1/auth/login. Throws {@link ApiError} (status 401) on bad credentials.
 * Never sends an existing stored token: login is public, and a stale-but-valid
 * token would make a "wrong password" response indistinguishable from a revoked
 * session (see `shared/api/client.ts`'s `skipAuth` option).
 */
export function login(credentials: LoginRequest): Promise<LoginResponse> {
  return apiPost<LoginResponse>('/api/v1/auth/login', credentials, { skipAuth: true });
}

/** POST /api/v1/auth/logout. Revokes every outstanding token for the caller. */
export async function logout(): Promise<void> {
  await apiPost('/api/v1/auth/logout');
}

/** GET /api/v1/auth/me. Throws {@link ApiError} (status 401) if the token is invalid. */
export function fetchCurrentUser(): Promise<User> {
  return apiGet<User>('/api/v1/auth/me');
}
