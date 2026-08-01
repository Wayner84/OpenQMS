/** Types for the NCR module, matching docs/API.md#ncr-module-milestone-4-in-progress. */

export type NcrType = 'internal' | 'supplier';

export type NcrStatus =
  'open' | 'investigate' | 'containment' | 'corrective_action' | 'verification' | 'closed';

/** The fixed one-directional sequence -- a transition may only move to the next
 * entry, never skip ahead or move backward. Mirrors
 * backend/app/modules/ncr/models.py::NCR_STATUS_SEQUENCE. */
export const NCR_STATUS_SEQUENCE: readonly NcrStatus[] = [
  'open',
  'investigate',
  'containment',
  'corrective_action',
  'verification',
  'closed',
];

export type NcrActionStatus = 'open' | 'complete';

export type NcrInvestigationToolType = 'five_why' | 'fishbone' | 'eight_d' | 'ten_d';

export interface Ncr {
  id: string;
  organisation_id: string;
  number: string;
  type: NcrType;
  product_id: string | null;
  supplier_id: string | null;
  status: NcrStatus;
  raised_by_id: string;
  description: string;
  root_cause_summary: string | null;
  created_by_id: string;
  updated_by_id: string;
  closed_at: string | null;
}

export interface NcrCreateRequest {
  type: NcrType;
  product_id?: string | null;
  supplier_id?: string | null;
  raised_by_id: string;
  description: string;
  root_cause_summary?: string | null;
}

export interface NcrUpdateRequest {
  type: NcrType;
  product_id?: string | null;
  supplier_id?: string | null;
  raised_by_id: string;
  description: string;
  root_cause_summary?: string | null;
}

export interface NcrListResponse {
  items: Ncr[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListNcrsParams {
  type?: NcrType;
  status?: NcrStatus;
  productId?: string;
  supplierId?: string;
  raisedById?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface NcrTransitionRequest {
  to_status: NcrStatus;
  comments?: string | null;
}

export interface NcrStatusHistoryEntry {
  id: string;
  ncr_id: string;
  from_status: NcrStatus | null;
  to_status: NcrStatus;
  changed_by_id: string;
  changed_at: string;
  comments: string | null;
}

export interface NcrStatusHistoryListResponse {
  items: NcrStatusHistoryEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface NcrAction {
  id: string;
  ncr_id: string;
  description: string;
  owner_id: string | null;
  due_date: string | null;
  status: NcrActionStatus;
  completed_at: string | null;
  created_by_id: string;
}

export interface NcrActionCreateRequest {
  description: string;
  owner_id?: string | null;
  due_date?: string | null;
}

export interface NcrActionUpdateRequest {
  description: string;
  owner_id?: string | null;
  due_date?: string | null;
  status: NcrActionStatus;
}

export interface NcrActionListResponse {
  items: NcrAction[];
  total: number;
  limit: number;
  offset: number;
}

export interface NcrInvestigationTool {
  id: string | null;
  ncr_id: string;
  tool_type: NcrInvestigationToolType;
  data: Record<string, unknown>;
  created_by_id: string | null;
  updated_by_id: string | null;
  updated_at: string | null;
}

export interface NcrAttachment {
  id: string;
  ncr_id: string;
  document_id: string;
  description: string | null;
  created_by_id: string;
}

export interface NcrAttachmentCreateRequest {
  document_id: string;
  description?: string | null;
}

export interface NcrAttachmentListResponse {
  items: NcrAttachment[];
  total: number;
  limit: number;
  offset: number;
}
