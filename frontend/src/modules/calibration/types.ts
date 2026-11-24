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
