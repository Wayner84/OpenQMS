import { apiDelete, apiGet, apiPatch, apiPost } from '../../shared/api/client';
import type {
  Asset,
  AssetListResponse,
  AssetWriteRequest,
  CalibrationSchedule,
  CalibrationScheduleCreate,
  CalibrationScheduleUpdate,
  ListAssetsParams,
  MaintenanceSchedule,
  MaintenanceScheduleCreate,
  MaintenanceScheduleUpdate,
  DueListResponse,
  ListDueParams,
} from './types';

/** Fetch a page of organisation-scoped calibration assets. */
export function listAssets(params: ListAssetsParams = {}): Promise<AssetListResponse> {
  const query = new URLSearchParams();
  if (params.assetType !== undefined) query.set('asset_type', params.assetType);
  if (params.status !== undefined) query.set('status', params.status);
  if (params.location !== undefined) query.set('location', params.location);
  if (params.search !== undefined) query.set('search', params.search);
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  const suffix = query.toString();
  return apiGet<AssetListResponse>(`/api/v1/calibration/assets${suffix ? `?${suffix}` : ''}`);
}

/** Create an asset within the authenticated user's organisation. */
export function createAsset(payload: AssetWriteRequest): Promise<Asset> {
  return apiPost<Asset>('/api/v1/calibration/assets', payload);
}

export function getAsset(id: string): Promise<Asset> {
  return apiGet<Asset>(`/api/v1/calibration/assets/${id}`);
}

/** Full replacement of editable fields: the backend PATCH uses AssetWriteRequest. */
export function updateAsset(id: string, payload: AssetWriteRequest): Promise<Asset> {
  return apiPatch<Asset>(`/api/v1/calibration/assets/${id}`, payload);
}

export function deleteAsset(id: string): Promise<void> {
  return apiDelete(`/api/v1/calibration/assets/${id}`);
}

export function getCalibrationSchedule(assetId: string): Promise<CalibrationSchedule> {
  return apiGet<CalibrationSchedule>(`/api/v1/calibration/assets/${assetId}/schedule`);
}

export function createCalibrationSchedule(
  assetId: string,
  payload: CalibrationScheduleCreate,
): Promise<CalibrationSchedule> {
  return apiPost<CalibrationSchedule>(`/api/v1/calibration/assets/${assetId}/schedule`, payload);
}

export function updateCalibrationSchedule(
  assetId: string,
  payload: CalibrationScheduleUpdate,
): Promise<CalibrationSchedule> {
  return apiPatch<CalibrationSchedule>(`/api/v1/calibration/assets/${assetId}/schedule`, payload);
}

const maintenancePath = (assetId: string): string =>
  `/api/v1/calibration/assets/${assetId}/maintenance-schedule`;

export function getMaintenanceSchedule(assetId: string): Promise<MaintenanceSchedule> {
  return apiGet<MaintenanceSchedule>(maintenancePath(assetId));
}

export function createMaintenanceSchedule(
  assetId: string,
  payload: MaintenanceScheduleCreate,
): Promise<MaintenanceSchedule> {
  return apiPost<MaintenanceSchedule>(maintenancePath(assetId), payload);
}

export function updateMaintenanceSchedule(
  assetId: string,
  payload: MaintenanceScheduleUpdate,
): Promise<MaintenanceSchedule> {
  return apiPatch<MaintenanceSchedule>(maintenancePath(assetId), payload);
}

export function listDue(params: ListDueParams = {}): Promise<DueListResponse> {
  const query = new URLSearchParams();
  if (params.withinDays !== undefined) query.set('within_days', String(params.withinDays));
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  const suffix = query.toString();
  return apiGet<DueListResponse>(`/api/v1/calibration/due${suffix ? `?${suffix}` : ''}`);
}
