/** Types for the Products module, matching docs/API.md#products-module-milestone-3. */

export type ProductType = 'internal' | 'purchased' | 'assembly' | 'component';
export type ProductDocumentRelationshipType = 'drawing' | 'specification' | 'cad';

export interface ProductCategory {
  id: string;
  organisation_id: string;
  name: string;
}

export interface ProductCategoryWriteRequest {
  name: string;
}

export interface ProductCategoryListResponse {
  items: ProductCategory[];
  total: number;
  limit: number;
  offset: number;
}

export interface Product {
  id: string;
  organisation_id: string;
  part_number: string;
  description: string;
  revision: string;
  category_id: string | null;
  type: ProductType;
  manufacturing_notes: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
}

export interface ProductWriteRequest {
  part_number: string;
  description: string;
  revision?: string;
  category_id?: string | null;
  type: ProductType;
  manufacturing_notes?: string | null;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListProductsParams {
  categoryId?: string;
  type?: ProductType;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface ProductDocumentLink {
  id: string;
  product_id: string;
  document_id: string;
  relationship_type: ProductDocumentRelationshipType;
}

export interface ProductDocumentLinkListResponse {
  items: ProductDocumentLink[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProductSupplierLink {
  id: string;
  product_id: string;
  supplier_id: string;
  is_preferred: boolean;
}

export interface ProductSupplierLinkListResponse {
  items: ProductSupplierLink[];
  total: number;
  limit: number;
  offset: number;
}
