/** Typed client functions for the NCR module, per docs/API.md#ncr-module-milestone-4-in-progress. */

import { apiDelete, apiGet, apiGetBlob, apiPatch, apiPost, apiPut } from '../../shared/api/client';
import type {
  ListNcrsParams,
  Ncr,
  NcrAction,
  NcrActionCreateRequest,
  NcrActionListResponse,
  NcrActionUpdateRequest,
  NcrAttachment,
  NcrAttachmentCreateRequest,
  NcrAttachmentListResponse,
  NcrCreateRequest,
  NcrInvestigationTool,
  NcrInvestigationToolType,
  NcrListResponse,
  NcrStatusHistoryListResponse,
  NcrTransitionRequest,
  NcrUpdateRequest,
} from './types';

function withPagination(params: { limit?: number; offset?: number }, query: URLSearchParams): void {
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
}

// --- NCRs ------------------------------------------------------------------------

/**
 * GET /api/v1/ncr (paginated, scoped to the caller's own organisation). Supports
 * `type`/`status`/`product_id`/`supplier_id`/`raised_by_id` exact filters and a
 * `search` substring across `number`/`description`.
 */
export function listNcrs(params: ListNcrsParams = {}): Promise<NcrListResponse> {
  const query = new URLSearchParams();
  if (params.type !== undefined) {
    query.set('type', params.type);
  }
  if (params.status !== undefined) {
    query.set('status', params.status);
  }
  if (params.productId !== undefined) {
    query.set('product_id', params.productId);
  }
  if (params.supplierId !== undefined) {
    query.set('supplier_id', params.supplierId);
  }
  if (params.raisedById !== undefined) {
    query.set('raised_by_id', params.raisedById);
  }
  if (params.search !== undefined) {
    query.set('search', params.search);
  }
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<NcrListResponse>(`/api/v1/ncr${queryString ? `?${queryString}` : ''}`);
}

/** GET /api/v1/ncr/{id}. Throws {@link ApiError} with status 404 for a cross-organisation id. */
export function getNcr(id: string): Promise<Ncr> {
  return apiGet<Ncr>(`/api/v1/ncr/${id}`);
}

/**
 * POST /api/v1/ncr. Throws {@link ApiError} with status 422 if `type`/`supplier_id`
 * violate the invariant (supplier NCRs require `supplier_id`, internal NCRs must
 * not set it), or 404 if `product_id`/`supplier_id`/`raised_by_id` don't exist in
 * the caller's own organisation.
 */
export function createNcr(payload: NcrCreateRequest): Promise<Ncr> {
  return apiPost<Ncr>('/api/v1/ncr', payload);
}

/** PATCH /api/v1/ncr/{id}. See {@link createNcr} for the error contract. */
export function updateNcr(id: string, payload: NcrUpdateRequest): Promise<Ncr> {
  return apiPatch<Ncr>(`/api/v1/ncr/${id}`, payload);
}

/** DELETE /api/v1/ncr/{id}. Admin-only. */
export function deleteNcr(id: string): Promise<void> {
  return apiDelete(`/api/v1/ncr/${id}`);
}

/**
 * POST /api/v1/ncr/{id}/transition. Throws {@link ApiError} with status 409 if
 * `to_status` is not exactly the next status in the fixed sequence, or if
 * transitioning to `closed` while any action is still `open`.
 */
export function transitionNcr(id: string, payload: NcrTransitionRequest): Promise<Ncr> {
  return apiPost<Ncr>(`/api/v1/ncr/${id}/transition`, payload);
}

/** GET /api/v1/ncr/{id}/status-history (paginated, chronological). */
export function listStatusHistory(
  id: string,
  params: { limit?: number; offset?: number } = {},
): Promise<NcrStatusHistoryListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<NcrStatusHistoryListResponse>(
    `/api/v1/ncr/${id}/status-history${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * GET /api/v1/ncr/{id}/export -- returns the rendered PDF report as a Blob, for a
 * browser-triggered download.
 */
export function exportNcr(id: string): Promise<Blob> {
  return apiGetBlob(`/api/v1/ncr/${id}/export`);
}

// --- Actions -----------------------------------------------------------------

/** GET /api/v1/ncr/{id}/actions (paginated). */
export function listActions(
  ncrId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<NcrActionListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<NcrActionListResponse>(
    `/api/v1/ncr/${ncrId}/actions${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * POST /api/v1/ncr/{id}/actions. Throws {@link ApiError} with status 409 if the
 * parent NCR is already `closed`.
 */
export function createAction(ncrId: string, payload: NcrActionCreateRequest): Promise<NcrAction> {
  return apiPost<NcrAction>(`/api/v1/ncr/${ncrId}/actions`, payload);
}

/** PATCH /api/v1/ncr/actions/{id}. See {@link createAction} for the error contract. */
export function updateAction(
  actionId: string,
  payload: NcrActionUpdateRequest,
): Promise<NcrAction> {
  return apiPatch<NcrAction>(`/api/v1/ncr/actions/${actionId}`, payload);
}

// --- Investigation tools -----------------------------------------------------

/** GET /api/v1/ncr/{id}/tools/{tool_type}. A tool that has never been saved
 * returns a default empty payload (`data: {}`, `id: null`), not a 404. */
export function getInvestigationTool(
  ncrId: string,
  toolType: NcrInvestigationToolType,
): Promise<NcrInvestigationTool> {
  return apiGet<NcrInvestigationTool>(`/api/v1/ncr/${ncrId}/tools/${toolType}`);
}

/**
 * PUT /api/v1/ncr/{id}/tools/{tool_type}. Creates-or-replaces `data`. Throws
 * {@link ApiError} with status 409 if the parent NCR is already `closed`.
 */
export function upsertInvestigationTool(
  ncrId: string,
  toolType: NcrInvestigationToolType,
  data: Record<string, unknown>,
): Promise<NcrInvestigationTool> {
  return apiPut<NcrInvestigationTool>(`/api/v1/ncr/${ncrId}/tools/${toolType}`, { data });
}

// --- Attachments ---------------------------------------------------------------

/** GET /api/v1/ncr/{id}/attachments (paginated). */
export function listAttachments(
  ncrId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<NcrAttachmentListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<NcrAttachmentListResponse>(
    `/api/v1/ncr/${ncrId}/attachments${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * POST /api/v1/ncr/{id}/attachments. Throws {@link ApiError} with status 404 if
 * `document_id` doesn't exist in the caller's own organisation, or 409 if it's
 * already attached, or if the parent NCR is already `closed`.
 */
export function createAttachment(
  ncrId: string,
  payload: NcrAttachmentCreateRequest,
): Promise<NcrAttachment> {
  return apiPost<NcrAttachment>(`/api/v1/ncr/${ncrId}/attachments`, payload);
}

/** DELETE /api/v1/ncr/{id}/attachments/{attachmentId}. See {@link createAttachment}
 * for the error contract. */
export function deleteAttachment(ncrId: string, attachmentId: string): Promise<void> {
  return apiDelete(`/api/v1/ncr/${ncrId}/attachments/${attachmentId}`);
}
