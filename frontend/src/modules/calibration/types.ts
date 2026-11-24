export type AssetType = 'measuring_equipment' | 'inspection_equipment' | 'company_asset';
export type AssetStatus = 'in_service' | 'out_of_service' | 'retired';

export interface Asset {
  id: string;
  organisation_id: string;
  asset_tag: string;
  name: string;
  asset_type: AssetType;
  serial_number: string | null;
  location: string | null;
  owner_id: string | null;
  status: AssetStatus;
  purchase_date: string | null;
  created_by_id: string;
  updated_by_id: string;
}

export interface AssetWriteRequest {
  asset_tag: string;
  name: string;
  asset_type: AssetType;
  serial_number?: string | null;
  location?: string | null;
  owner_id?: string | null;
  status?: AssetStatus;
  purchase_date?: string | null;
}

export interface AssetListResponse {
  items: Asset[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListAssetsParams {
  assetType?: AssetType;
  status?: AssetStatus;
  location?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export type CalibrationIntervalUnit = 'days' | 'months' | 'years';

export interface CalibrationSchedule {
  id: string;
  asset_id: string;
  interval_value: number;
  interval_unit: CalibrationIntervalUnit;
  next_due_date: string | null;
  created_by_id: string;
  updated_by_id: string;
}

export interface CalibrationScheduleCreate {
  interval_value: number;
  interval_unit: CalibrationIntervalUnit;
}

export interface CalibrationScheduleUpdate extends CalibrationScheduleCreate {
  next_due_date: string | null;
}

/** GET returns null fields when no maintenance schedule exists. */
export interface MaintenanceSchedule {
  id: string | null;
  asset_id: string;
  interval_value: number | null;
  interval_unit: CalibrationIntervalUnit | null;
  next_due_date: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
}

export interface MaintenanceScheduleCreate {
  interval_value: number;
  interval_unit: CalibrationIntervalUnit;
  next_due_date: string | null;
}

/** PATCH only changes supplied fields; explicit null clears the due date. */
export interface MaintenanceScheduleUpdate {
  interval_value?: number;
  interval_unit?: CalibrationIntervalUnit;
  next_due_date?: string | null;
}

export interface DueItem {
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  due_type: 'calibration' | 'maintenance';
  next_due_date: string;
}

export interface DueListResponse {
  items: DueItem[];
  total: number;
  limit: number;
  offset: number;
  within_days: number;
}

export interface ListDueParams {
  withinDays?: number;
  limit?: number;
  offset?: number;
}

export type CalibrationResult = 'pass' | 'fail' | 'limited';
export interface CalibrationEventCreate {
  performed_at: string;
  performed_by_id: string | null;
  performed_by_supplier_id: string | null;
  certificate_document_id: string | null;
  result: CalibrationResult;
  notes: string | null;
}
export interface CalibrationEvent extends CalibrationEventCreate {
  id: string;
  asset_id: string;
  next_due_date: string | null;
  created_by_id: string;
}
export interface CalibrationEventListResponse {
  items: CalibrationEvent[];
  total: number;
  limit: number;
  offset: number;
}
