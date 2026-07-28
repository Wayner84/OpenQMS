/** Types for the Document Management module, matching docs/API.md#document-management-milestone-2-in-progress. */

export type DocumentStatus = 'draft' | 'in_review' | 'approved' | 'obsolete';

export type DocumentVersionStatus = 'draft' | 'in_review' | 'approved' | 'rejected' | 'obsolete';

export interface Category {
  id: string;
  organisation_id: string;
  name: string;
  parent_category_id: string | null;
}

export interface CategoryWriteRequest {
  name: string;
  parent_category_id?: string | null;
}

export interface CategoryListResponse {
  items: Category[];
  total: number;
  limit: number;
  offset: number;
}

export interface Tag {
  id: string;
  organisation_id: string;
  name: string;
}

export interface TagListResponse {
  items: Tag[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentRecord {
  id: string;
  organisation_id: string;
  category_id: string | null;
  number: string;
  title: string;
  owner_id: string | null;
  status: DocumentStatus;
  current_version_id: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
  tags: Tag[];
}

export interface DocumentWriteRequest {
  title: string;
  category_id?: string | null;
  owner_id?: string | null;
  tag_ids?: string[];
}

export interface DocumentListResponse {
  items: DocumentRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListDocumentsParams {
  categoryId?: string;
  status?: DocumentStatus;
  ownerId?: string;
  search?: string;
  tag?: string;
  limit?: number;
  offset?: number;
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  change_summary: string | null;
  status: DocumentVersionStatus;
  created_by_id: string | null;
  created_at: string;
}

export interface DocumentVersionListResponse {
  items: DocumentVersion[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentAcknowledgement {
  id: string;
  document_version_id: string;
  acknowledged_by_id: string;
  acknowledged_at: string;
}

export interface DocumentAcknowledgementListResponse {
  items: DocumentAcknowledgement[];
  total: number;
  limit: number;
  offset: number;
}

export interface VersionComparisonResponse {
  version_a: DocumentVersion;
  version_b: DocumentVersion;
  checksum_changed: boolean;
  text_diff: string[] | null;
}

/** The content types the backend will stream `inline` from the preview endpoint;
 * anything else must use download instead. Mirrors
 * backend/app/modules/documents/storage.py::PREVIEWABLE_CONTENT_TYPES -- a
 * client-side hint only, the server is still the authority (`415` otherwise). */
export const PREVIEWABLE_CONTENT_TYPES: ReadonlySet<string> = new Set([
  'application/pdf',
  'image/png',
  'image/jpeg',
]);
