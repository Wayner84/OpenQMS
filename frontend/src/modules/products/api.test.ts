import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearToken, setToken } from '../../shared/auth/tokenStore';
import {
  createProduct,
  createProductCategory,
  createProductDocumentLink,
  createProductSupplierLink,
  deleteProduct,
  deleteProductCategory,
  deleteProductDocumentLink,
  deleteProductSupplierLink,
  getProduct,
  listProductCategories,
  listProductDocumentLinks,
  listProducts,
  listProductSupplierLinks,
  updateProduct,
  updateProductCategory,
} from './api';

describe('products api', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubGlobal('fetch', vi.fn());
    setToken('a.jwt.token');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    clearToken();
  });

  describe('categories', () => {
    it('lists, creates, updates, and deletes a category', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );
      await listProductCategories();
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/product-categories',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'cat1' }), { status: 201 }),
      );
      await createProductCategory({ name: 'Fasteners' });
      expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe(
        'http://localhost:8000/api/v1/product-categories',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'cat1' }), { status: 200 }),
      );
      await updateProductCategory('cat1', { name: 'Hardware' });
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe(
        'http://localhost:8000/api/v1/product-categories/cat1',
      );

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      await deleteProductCategory('cat1');
      expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe(
        'http://localhost:8000/api/v1/product-categories/cat1',
      );
    });
  });

  describe('listProducts', () => {
    it('requests the default page when called with no arguments', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );

      await listProducts();

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/products');
    });

    it('encodes every filter as a query parameter', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 }), {
          status: 200,
        }),
      );

      await listProducts({
        categoryId: 'cat1',
        type: 'internal',
        search: 'bolt',
        limit: 20,
        offset: 0,
      });

      const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        'http://localhost:8000/api/v1/products?category_id=cat1&type=internal&search=bolt&limit=20&offset=0',
      );
    });
  });

  describe('product CRUD', () => {
    it('gets, creates, updates, and deletes a product', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'p1' }), { status: 200 }),
      );
      await getProduct('p1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe('http://localhost:8000/api/v1/products/p1');

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'p1' }), { status: 201 }),
      );
      await createProduct({ part_number: 'PN-1', description: 'Widget', type: 'internal' });
      expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe('http://localhost:8000/api/v1/products');

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'p1' }), { status: 200 }),
      );
      await updateProduct('p1', { part_number: 'PN-1', description: 'Widget', type: 'internal' });
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe('http://localhost:8000/api/v1/products/p1');

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      await deleteProduct('p1');
      expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe('http://localhost:8000/api/v1/products/p1');
    });
  });

  describe('document links', () => {
    it('lists, creates, and deletes a document link', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );
      await listProductDocumentLinks('p1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/products/p1/documents',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'link1' }), { status: 201 }),
      );
      await createProductDocumentLink('p1', 'd1', 'drawing');
      const [url, init] = vi.mocked(fetch).mock.calls[1] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/products/p1/documents');
      expect(JSON.parse(init?.body as string)).toEqual({
        document_id: 'd1',
        relationship_type: 'drawing',
      });

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      await deleteProductDocumentLink('p1', 'link1');
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe(
        'http://localhost:8000/api/v1/products/p1/documents/link1',
      );
    });
  });

  describe('supplier links', () => {
    it('lists, creates, and deletes a supplier link', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
          status: 200,
        }),
      );
      await listProductSupplierLinks('p1');
      expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
        'http://localhost:8000/api/v1/products/p1/suppliers',
      );

      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ id: 'link1' }), { status: 201 }),
      );
      await createProductSupplierLink('p1', 's1', true);
      const [url, init] = vi.mocked(fetch).mock.calls[1] ?? [];
      expect(url).toBe('http://localhost:8000/api/v1/products/p1/suppliers');
      expect(JSON.parse(init?.body as string)).toEqual({ supplier_id: 's1', is_preferred: true });

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      await deleteProductSupplierLink('p1', 'link1');
      expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe(
        'http://localhost:8000/api/v1/products/p1/suppliers/link1',
      );
    });
  });
});
