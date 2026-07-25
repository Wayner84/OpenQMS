/** Typed client functions for the platform health endpoints, per docs/API.md. */

import { ApiError, apiGet } from './client';

export interface LivenessResponse {
  status: string;
}

export interface ReadinessResponse {
  status: string;
  database: string;
}

/** Liveness probe: GET /api/v1/health. Does not touch the database. */
export function getHealth(): Promise<LivenessResponse> {
  return apiGet<LivenessResponse>('/api/v1/health');
}

/**
 * Readiness probe: GET /api/v1/health/ready. A `503` is a documented "not ready"
 * response with a meaningful body (see docs/API.md#get-apiv1healthready), not a
 * transport failure, so it is resolved rather than rejected.
 */
export async function getReadiness(): Promise<ReadinessResponse> {
  try {
    return await apiGet<ReadinessResponse>('/api/v1/health/ready');
  } catch (error) {
    if (error instanceof ApiError && error.status === 503 && error.body) {
      return error.body as ReadinessResponse;
    }
    throw error;
  }
}
