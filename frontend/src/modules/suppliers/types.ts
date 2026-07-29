/** Types for the Suppliers module, matching docs/API.md#suppliers-module-milestone-3. */

export type ApprovalStatus = 'approved' | 'pending' | 'suspended';
export type RiskRating = 'low' | 'medium' | 'high';

export interface Supplier {
  id: string;
  organisation_id: string;
  company_id: string;
  approval_status: ApprovalStatus;
  risk_rating: RiskRating | null;
  is_preferred: boolean;
  notes: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
}

export interface SupplierWriteRequest {
  company_id: string;
  approval_status: ApprovalStatus;
  risk_rating?: RiskRating | null;
  is_preferred: boolean;
  notes?: string | null;
}

export interface SupplierListResponse {
  items: Supplier[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListSuppliersParams {
  approvalStatus?: ApprovalStatus;
  riskRating?: RiskRating;
  isPreferred?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface SupplierCertification {
  id: string;
  supplier_id: string;
  certification_type: string;
  certificate_document_id: string | null;
  issued_date: string | null;
  expiry_date: string | null;
}

export interface SupplierCertificationWriteRequest {
  certification_type: string;
  certificate_document_id?: string | null;
  issued_date?: string | null;
  expiry_date?: string | null;
}

export interface SupplierCertificationListResponse {
  items: SupplierCertification[];
  total: number;
  limit: number;
  offset: number;
}

export interface SupplierPerformanceRecord {
  id: string;
  supplier_id: string;
  period: string;
  score: string;
  notes: string | null;
  created_by_id: string | null;
}

export interface SupplierPerformanceRecordWriteRequest {
  period: string;
  score: string;
  notes?: string | null;
}

export interface SupplierPerformanceRecordListResponse {
  items: SupplierPerformanceRecord[];
  total: number;
  limit: number;
  offset: number;
}
