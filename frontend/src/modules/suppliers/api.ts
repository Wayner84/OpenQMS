/** Typed client functions for the Suppliers module, per docs/API.md#suppliers-module-milestone-3. */

import { apiDelete, apiGet, apiPatch, apiPost } from '../../shared/api/client';
import type { NcrListResponse } from '../ncr/types';
import type {
  ListSuppliersParams,
  Supplier,
  SupplierCertification,
  SupplierCertificationListResponse,
  SupplierCertificationWriteRequest,
  SupplierListResponse,
  SupplierPerformanceRecord,
  SupplierPerformanceRecordListResponse,
  SupplierPerformanceRecordWriteRequest,
  SupplierWriteRequest,
} from './types';

/** GET /api/v1/suppliers (paginated, scoped to the caller's own organisation). */
export function listSuppliers(params: ListSuppliersParams = {}): Promise<SupplierListResponse> {
  const query = new URLSearchParams();
  if (params.approvalStatus !== undefined) {
    query.set('approval_status', params.approvalStatus);
  }
  if (params.riskRating !== undefined) {
    query.set('risk_rating', params.riskRating);
  }
  if (params.isPreferred !== undefined) {
    query.set('is_preferred', String(params.isPreferred));
  }
  if (params.search !== undefined) {
    query.set('search', params.search);
  }
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<SupplierListResponse>(`/api/v1/suppliers${queryString ? `?${queryString}` : ''}`);
}

/** GET /api/v1/suppliers/{id}. Throws {@link ApiError} with status 404 for a cross-organisation id. */
export function getSupplier(id: string): Promise<Supplier> {
  return apiGet<Supplier>(`/api/v1/suppliers/${id}`);
}

/**
 * POST /api/v1/suppliers. Throws {@link ApiError} with status 404 if `company_id`
 * doesn't exist in the caller's own organisation.
 */
export function createSupplier(payload: SupplierWriteRequest): Promise<Supplier> {
  return apiPost<Supplier>('/api/v1/suppliers', payload);
}

/** PATCH /api/v1/suppliers/{id}. See {@link createSupplier} for the error contract. */
export function updateSupplier(id: string, payload: SupplierWriteRequest): Promise<Supplier> {
  return apiPatch<Supplier>(`/api/v1/suppliers/${id}`, payload);
}

/** DELETE /api/v1/suppliers/{id}. Throws {@link ApiError} with status 404 for a cross-organisation id. */
export function deleteSupplier(id: string): Promise<void> {
  return apiDelete(`/api/v1/suppliers/${id}`);
}

/** GET /api/v1/suppliers/{id}/certifications (paginated). */
export function listCertifications(
  supplierId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<SupplierCertificationListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<SupplierCertificationListResponse>(
    `/api/v1/suppliers/${supplierId}/certifications${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * POST /api/v1/suppliers/{id}/certifications. Throws {@link ApiError} with status
 * 404 if `certificate_document_id` doesn't exist in the caller's own organisation.
 */
export function createCertification(
  supplierId: string,
  payload: SupplierCertificationWriteRequest,
): Promise<SupplierCertification> {
  return apiPost<SupplierCertification>(`/api/v1/suppliers/${supplierId}/certifications`, payload);
}

/** PATCH /api/v1/suppliers/{id}/certifications/{certificationId}. */
export function updateCertification(
  supplierId: string,
  certificationId: string,
  payload: SupplierCertificationWriteRequest,
): Promise<SupplierCertification> {
  return apiPatch<SupplierCertification>(
    `/api/v1/suppliers/${supplierId}/certifications/${certificationId}`,
    payload,
  );
}

/** DELETE /api/v1/suppliers/{id}/certifications/{certificationId}. */
export function deleteCertification(supplierId: string, certificationId: string): Promise<void> {
  return apiDelete(`/api/v1/suppliers/${supplierId}/certifications/${certificationId}`);
}

/**
 * GET /api/v1/suppliers/certifications/expiring?within_days= — certifications
 * expiring within `withinDays` days (or the organisation's configured default),
 * soonest first, across every supplier in the caller's organisation.
 */
export function listExpiringCertifications(
  params: { withinDays?: number; limit?: number; offset?: number } = {},
): Promise<SupplierCertificationListResponse> {
  const query = new URLSearchParams();
  if (params.withinDays !== undefined) {
    query.set('within_days', String(params.withinDays));
  }
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<SupplierCertificationListResponse>(
    `/api/v1/suppliers/certifications/expiring${queryString ? `?${queryString}` : ''}`,
  );
}

/** GET /api/v1/suppliers/{id}/performance (paginated, newest first). */
export function listPerformanceRecords(
  supplierId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<SupplierPerformanceRecordListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<SupplierPerformanceRecordListResponse>(
    `/api/v1/suppliers/${supplierId}/performance${queryString ? `?${queryString}` : ''}`,
  );
}

/** POST /api/v1/suppliers/{id}/performance. Append-only — there is no update/delete route. */
export function createPerformanceRecord(
  supplierId: string,
  payload: SupplierPerformanceRecordWriteRequest,
): Promise<SupplierPerformanceRecord> {
  return apiPost<SupplierPerformanceRecord>(`/api/v1/suppliers/${supplierId}/performance`, payload);
}

/** GET /api/v1/suppliers/{id}/ncr-history (paginated, read-only). */
export function listNcrHistory(
  supplierId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<NcrListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<NcrListResponse>(
    `/api/v1/suppliers/${supplierId}/ncr-history${queryString ? `?${queryString}` : ''}`,
  );
}
