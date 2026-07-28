/** Typed client functions for the Document Management module, per
 * docs/API.md#document-management-milestone-2-in-progress. */

import {
  apiDelete,
  apiGet,
  apiGetBlob,
  apiPatch,
  apiPost,
  apiPostForm,
} from '../../shared/api/client';
import type {
  Category,
  CategoryListResponse,
  CategoryWriteRequest,
  DocumentAcknowledgement,
  DocumentAcknowledgementListResponse,
  DocumentListResponse,
  DocumentRecord,
  DocumentVersion,
  DocumentVersionListResponse,
  DocumentWriteRequest,
  ListDocumentsParams,
  Tag,
  TagListResponse,
  VersionComparisonResponse,
} from './types';

function withPagination(params: { limit?: number; offset?: number }, query: URLSearchParams): void {
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
}

// --- Categories ----------------------------------------------------------------

/** GET /api/v1/document-categories (paginated, scoped to the caller's own organisation). */
export function listCategories(
  params: { limit?: number; offset?: number } = {},
): Promise<CategoryListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<CategoryListResponse>(
    `/api/v1/document-categories${queryString ? `?${queryString}` : ''}`,
  );
}

/** POST /api/v1/document-categories. **Admin only** -- throws {@link ApiError} with status 403 otherwise. */
export function createCategory(payload: CategoryWriteRequest): Promise<Category> {
  return apiPost<Category>('/api/v1/document-categories', payload);
}

/** PATCH /api/v1/document-categories/{id}. **Admin only**. */
export function updateCategory(id: string, payload: CategoryWriteRequest): Promise<Category> {
  return apiPatch<Category>(`/api/v1/document-categories/${id}`, payload);
}

/**
 * DELETE /api/v1/document-categories/{id}. **Admin only**. Throws {@link ApiError}
 * with status 409 if the category still has child categories or is referenced by a
 * document.
 */
export function deleteCategory(id: string): Promise<void> {
  return apiDelete(`/api/v1/document-categories/${id}`);
}

// --- Tags ------------------------------------------------------------------

/** GET /api/v1/document-tags (paginated, optional `search` substring match). */
export function listTags(
  params: { search?: string; limit?: number; offset?: number } = {},
): Promise<TagListResponse> {
  const query = new URLSearchParams();
  if (params.search !== undefined) {
    query.set('search', params.search);
  }
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<TagListResponse>(`/api/v1/document-tags${queryString ? `?${queryString}` : ''}`);
}

/** POST /api/v1/document-tags. **Admin only**. Throws {@link ApiError} with status 409 for a duplicate name. */
export function createTag(payload: { name: string }): Promise<Tag> {
  return apiPost<Tag>('/api/v1/document-tags', payload);
}

/** DELETE /api/v1/document-tags/{id}. **Admin only**. Cascades: unlinks the tag from every document. */
export function deleteTag(id: string): Promise<void> {
  return apiDelete(`/api/v1/document-tags/${id}`);
}

// --- Documents ---------------------------------------------------------------

/**
 * GET /api/v1/documents (paginated, scoped to the caller's own organisation).
 * Supports `category_id`/`status`/`owner_id` exact filters, `search` (substring
 * across title/number), and `tag` (exact name), all combinable.
 */
export function listDocuments(params: ListDocumentsParams = {}): Promise<DocumentListResponse> {
  const query = new URLSearchParams();
  if (params.categoryId !== undefined) {
    query.set('category_id', params.categoryId);
  }
  if (params.status !== undefined) {
    query.set('status', params.status);
  }
  if (params.ownerId !== undefined) {
    query.set('owner_id', params.ownerId);
  }
  if (params.search !== undefined) {
    query.set('search', params.search);
  }
  if (params.tag !== undefined) {
    query.set('tag', params.tag);
  }
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<DocumentListResponse>(`/api/v1/documents${queryString ? `?${queryString}` : ''}`);
}

/** POST /api/v1/documents. Any active user. `number` is always server-generated. */
export function createDocument(payload: DocumentWriteRequest): Promise<DocumentRecord> {
  return apiPost<DocumentRecord>('/api/v1/documents', payload);
}

/** GET /api/v1/documents/{id}. Throws {@link ApiError} with status 404 for a cross-organisation id. */
export function getDocument(id: string): Promise<DocumentRecord> {
  return apiGet<DocumentRecord>(`/api/v1/documents/${id}`);
}

/** PATCH /api/v1/documents/{id}. Any active user. See {@link getDocument} for the error contract. */
export function updateDocument(id: string, payload: DocumentWriteRequest): Promise<DocumentRecord> {
  return apiPatch<DocumentRecord>(`/api/v1/documents/${id}`, payload);
}

/** DELETE /api/v1/documents/{id}. **Admin only**. Soft delete. */
export function deleteDocument(id: string): Promise<void> {
  return apiDelete(`/api/v1/documents/${id}`);
}

// --- Versions ----------------------------------------------------------------

/** GET /api/v1/documents/{id}/versions (paginated, newest first). */
export function listDocumentVersions(
  documentId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<DocumentVersionListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<DocumentVersionListResponse>(
    `/api/v1/documents/${documentId}/versions${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * POST /api/v1/documents/{id}/versions -- uploads a new, immutable version. Any
 * active user. Throws {@link ApiError} with status 422 for a disallowed extension
 * or a signature/extension mismatch, 413 if the file is too large.
 */
export function uploadDocumentVersion(
  documentId: string,
  file: File,
  changeSummary?: string,
): Promise<DocumentVersion> {
  const formData = new FormData();
  formData.set('file', file);
  if (changeSummary) {
    formData.set('change_summary', changeSummary);
  }
  return apiPostForm<DocumentVersion>(`/api/v1/documents/${documentId}/versions`, formData);
}

/** GET .../download -- returns the raw file bytes as a Blob, for a browser-triggered download. */
export function downloadDocumentVersion(documentId: string, versionId: string): Promise<Blob> {
  return apiGetBlob(`/api/v1/documents/${documentId}/versions/${versionId}/download`);
}

/**
 * GET .../preview -- returns the raw file bytes as a Blob for inline rendering.
 * Throws {@link ApiError} with status 415 for a non-previewable content type; check
 * {@link PREVIEWABLE_CONTENT_TYPES} first to avoid the round trip, though the
 * server is still the authority.
 */
export function previewDocumentVersion(documentId: string, versionId: string): Promise<Blob> {
  return apiGetBlob(`/api/v1/documents/${documentId}/versions/${versionId}/preview`);
}

// --- Workflow ------------------------------------------------------------------

/** POST .../submit-for-approval. Any active user. `draft` -> `in_review`. */
export function submitVersionForApproval(
  documentId: string,
  versionId: string,
): Promise<DocumentVersion> {
  return apiPost<DocumentVersion>(
    `/api/v1/documents/${documentId}/versions/${versionId}/submit-for-approval`,
  );
}

/** POST .../approve. **Admin only**. `in_review` -> `approved`. */
export function approveVersion(
  documentId: string,
  versionId: string,
  comments?: string,
): Promise<DocumentVersion> {
  return apiPost<DocumentVersion>(`/api/v1/documents/${documentId}/versions/${versionId}/approve`, {
    comments: comments || undefined,
  });
}

/** POST .../reject. **Admin only**. `in_review` -> `rejected`. `comments` is required. */
export function rejectVersion(
  documentId: string,
  versionId: string,
  comments: string,
): Promise<DocumentVersion> {
  return apiPost<DocumentVersion>(`/api/v1/documents/${documentId}/versions/${versionId}/reject`, {
    comments,
  });
}

/** POST /api/v1/documents/{id}/obsolete. **Admin only**. Retires the whole document. */
export function retireDocument(documentId: string): Promise<DocumentRecord> {
  return apiPost<DocumentRecord>(`/api/v1/documents/${documentId}/obsolete`);
}

// --- Acknowledgements ------------------------------------------------------------

/** POST .../acknowledge. Any active user, self-only, idempotent. */
export function acknowledgeVersion(
  documentId: string,
  versionId: string,
): Promise<DocumentAcknowledgement> {
  return apiPost<DocumentAcknowledgement>(
    `/api/v1/documents/${documentId}/versions/${versionId}/acknowledge`,
  );
}

/** GET .../acknowledgements (paginated). Any active user. */
export function listVersionAcknowledgements(
  documentId: string,
  versionId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<DocumentAcknowledgementListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<DocumentAcknowledgementListResponse>(
    `/api/v1/documents/${documentId}/versions/${versionId}/acknowledgements${
      queryString ? `?${queryString}` : ''
    }`,
  );
}

// --- Comparison ------------------------------------------------------------------

/** GET .../versions/{a}/compare/{b}. Any active user. */
export function compareVersions(
  documentId: string,
  versionAId: string,
  versionBId: string,
): Promise<VersionComparisonResponse> {
  return apiGet<VersionComparisonResponse>(
    `/api/v1/documents/${documentId}/versions/${versionAId}/compare/${versionBId}`,
  );
}
