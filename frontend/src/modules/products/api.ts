/** Typed client functions for the Products module, per docs/API.md#products-module-milestone-3. */

import { apiDelete, apiGet, apiPatch, apiPost } from '../../shared/api/client';
import type {
  ListProductsParams,
  Product,
  ProductCategory,
  ProductCategoryListResponse,
  ProductCategoryWriteRequest,
  ProductDocumentLink,
  ProductDocumentLinkListResponse,
  ProductDocumentRelationshipType,
  ProductListResponse,
  ProductSupplierLink,
  ProductSupplierLinkListResponse,
  ProductWriteRequest,
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

/** GET /api/v1/product-categories (paginated, alphabetical). */
export function listProductCategories(
  params: { limit?: number; offset?: number } = {},
): Promise<ProductCategoryListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<ProductCategoryListResponse>(
    `/api/v1/product-categories${queryString ? `?${queryString}` : ''}`,
  );
}

/** POST /api/v1/product-categories. Any active user. */
export function createProductCategory(
  payload: ProductCategoryWriteRequest,
): Promise<ProductCategory> {
  return apiPost<ProductCategory>('/api/v1/product-categories', payload);
}

/** PATCH /api/v1/product-categories/{id}. */
export function updateProductCategory(
  id: string,
  payload: ProductCategoryWriteRequest,
): Promise<ProductCategory> {
  return apiPatch<ProductCategory>(`/api/v1/product-categories/${id}`, payload);
}

/**
 * DELETE /api/v1/product-categories/{id}. Throws {@link ApiError} with status 409
 * if any product still references this category.
 */
export function deleteProductCategory(id: string): Promise<void> {
  return apiDelete(`/api/v1/product-categories/${id}`);
}

// --- Products --------------------------------------------------------------------

/**
 * GET /api/v1/products (paginated, scoped to the caller's own organisation).
 * Supports `category_id`/`type` exact filters and a `search` substring across
 * `part_number`/`description`.
 */
export function listProducts(params: ListProductsParams = {}): Promise<ProductListResponse> {
  const query = new URLSearchParams();
  if (params.categoryId !== undefined) {
    query.set('category_id', params.categoryId);
  }
  if (params.type !== undefined) {
    query.set('type', params.type);
  }
  if (params.search !== undefined) {
    query.set('search', params.search);
  }
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<ProductListResponse>(`/api/v1/products${queryString ? `?${queryString}` : ''}`);
}

/** GET /api/v1/products/{id}. Throws {@link ApiError} with status 404 for a cross-organisation id. */
export function getProduct(id: string): Promise<Product> {
  return apiGet<Product>(`/api/v1/products/${id}`);
}

/**
 * POST /api/v1/products. Throws {@link ApiError} with status 409 for a duplicate
 * `part_number` within the caller's organisation.
 */
export function createProduct(payload: ProductWriteRequest): Promise<Product> {
  return apiPost<Product>('/api/v1/products', payload);
}

/** PATCH /api/v1/products/{id}. See {@link createProduct} for the error contract. */
export function updateProduct(id: string, payload: ProductWriteRequest): Promise<Product> {
  return apiPatch<Product>(`/api/v1/products/${id}`, payload);
}

/** DELETE /api/v1/products/{id}. Throws {@link ApiError} with status 404 for a cross-organisation id. */
export function deleteProduct(id: string): Promise<void> {
  return apiDelete(`/api/v1/products/${id}`);
}

// --- Document links --------------------------------------------------------------

/** GET /api/v1/products/{id}/documents (paginated). */
export function listProductDocumentLinks(
  productId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<ProductDocumentLinkListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<ProductDocumentLinkListResponse>(
    `/api/v1/products/${productId}/documents${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * POST /api/v1/products/{id}/documents. Throws {@link ApiError} with status 404 if
 * `document_id` doesn't exist in the caller's own organisation, or 409 if this
 * exact (document, relationship type) pair is already linked.
 */
export function createProductDocumentLink(
  productId: string,
  documentId: string,
  relationshipType: ProductDocumentRelationshipType,
): Promise<ProductDocumentLink> {
  return apiPost<ProductDocumentLink>(`/api/v1/products/${productId}/documents`, {
    document_id: documentId,
    relationship_type: relationshipType,
  });
}

/** DELETE /api/v1/products/{id}/documents/{linkId}. Unlinks without affecting the document itself. */
export function deleteProductDocumentLink(productId: string, linkId: string): Promise<void> {
  return apiDelete(`/api/v1/products/${productId}/documents/${linkId}`);
}

// --- Supplier links ----------------------------------------------------------------

/** GET /api/v1/products/{id}/suppliers (paginated). */
export function listProductSupplierLinks(
  productId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<ProductSupplierLinkListResponse> {
  const query = new URLSearchParams();
  withPagination(params, query);
  const queryString = query.toString();
  return apiGet<ProductSupplierLinkListResponse>(
    `/api/v1/products/${productId}/suppliers${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * POST /api/v1/products/{id}/suppliers. Throws {@link ApiError} with status 404 if
 * `supplierId` doesn't exist in the caller's own organisation, or 409 if this
 * supplier is already linked.
 */
export function createProductSupplierLink(
  productId: string,
  supplierId: string,
  isPreferred: boolean,
): Promise<ProductSupplierLink> {
  return apiPost<ProductSupplierLink>(`/api/v1/products/${productId}/suppliers`, {
    supplier_id: supplierId,
    is_preferred: isPreferred,
  });
}

/** DELETE /api/v1/products/{id}/suppliers/{linkId}. */
export function deleteProductSupplierLink(productId: string, linkId: string): Promise<void> {
  return apiDelete(`/api/v1/products/${productId}/suppliers/${linkId}`);
}
