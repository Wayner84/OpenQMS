/** Typed client functions for the user management module, per docs/API.md#user-management-milestone-1. */

import { apiGet, apiPatch, apiPost } from '../../shared/api/client';
import type { User } from '../auth/types';
import type { CreateUserRequest, UpdateUserRequest, UserListResponse } from './types';

/** GET /api/v1/users (admin-only, paginated, scoped to the caller's own organisation). */
export function listUsers(
  params: { limit?: number; offset?: number } = {},
): Promise<UserListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<UserListResponse>(`/api/v1/users${queryString ? `?${queryString}` : ''}`);
}

/** POST /api/v1/users (admin-only). Throws {@link ApiError} (status 409) on a duplicate email. */
export function createUser(payload: CreateUserRequest): Promise<User> {
  return apiPost<User>('/api/v1/users', payload);
}

/**
 * PATCH /api/v1/users/{id} (admin-only). Throws {@link ApiError} with status 404 for a
 * cross-organisation id, or 409 for the self-deactivation/last-admin guards — the
 * server's `detail` message is shown to the caller rather than re-implemented here.
 */
export function updateUser(id: string, payload: UpdateUserRequest): Promise<User> {
  return apiPatch<User>(`/api/v1/users/${id}`, payload);
}
