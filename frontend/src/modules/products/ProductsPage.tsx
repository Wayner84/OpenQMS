import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { createProduct, listProductCategories, listProducts } from './api';
import type { Product, ProductCategory, ProductType } from './types';

const DEFAULT_PAGE_SIZE = 20;

const TYPE_LABELS: Record<ProductType, string> = {
  internal: 'Internal',
  purchased: 'Purchased',
  assembly: 'Assembly',
  component: 'Component',
};

interface CreateForm {
  partNumber: string;
  description: string;
  revision: string;
  categoryId: string;
  type: ProductType;
  manufacturingNotes: string;
}

const emptyForm: CreateForm = {
  partNumber: '',
  description: '',
  revision: 'A',
  categoryId: '',
  type: 'internal',
  manufacturingNotes: '',
};

/**
 * The product register: searchable/filterable list (any active user) and a
 * create-product form. Category administration is reachable from here (not
 * admin-gated -- see the Milestone 3 plan's design decision 2).
 */
export function ProductsPage({
  pageSize = DEFAULT_PAGE_SIZE,
}: {
  pageSize?: number;
}): ReactElement {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState<ProductType | ''>('');
  const [form, setForm] = useState<CreateForm>(emptyForm);
  const [creating, setCreating] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);
  const optionsRequestIdRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const requestId = ++optionsRequestIdRef.current;
    setOptionsError(null);
    void fetchAllPages<ProductCategory>((params) => listProductCategories(params))
      .then((items) => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setCategories(items);
        }
      })
      .catch(() => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setOptionsError('Could not load categories. Please try again.');
        }
      });
  }, [refreshVersion]);

  const categoryNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const category of categories) {
      map.set(category.id, category.name);
    }
    return map;
  }, [categories]);

  const loadPage = useCallback(
    async (nextOffset: number) => {
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listProducts({
          limit: pageSize,
          offset: nextOffset,
          search: searchTerm || undefined,
          categoryId: categoryFilter || undefined,
          type: typeFilter || undefined,
        });
        if (mountedRef.current && requestIdRef.current === requestId) {
          setProducts(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoadError('Could not load products. Please try again.');
        }
      } finally {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoading(false);
        }
      }
    },
    [pageSize, searchTerm, categoryFilter, typeFilter],
  );

  useEffect(() => {
    void loadPage(0);
  }, [loadPage, refreshVersion]);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setSearchTerm(searchInput);
  };

  const handleCreate = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setActionError(null);
    setCreating(true);
    void (async () => {
      try {
        await createProduct({
          part_number: form.partNumber,
          description: form.description,
          revision: form.revision || undefined,
          category_id: form.categoryId || undefined,
          type: form.type,
          manufacturing_notes: form.manufacturingNotes || undefined,
        });
        if (mountedRef.current) {
          setForm(emptyForm);
        }
        setRefreshVersion((current) => current + 1);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not create the product. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setCreating(false);
        }
      }
    })();
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + products.length < total;

  return (
    <section>
      <h2>Products</h2>
      <p>
        <Link to="/products/categories">Manage categories</Link>
      </p>
      {actionError && (
        <p role="alert" className="auth-form__error">
          {actionError}
        </p>
      )}
      {optionsError && (
        <p role="alert" className="auth-form__error">
          {optionsError}
        </p>
      )}

      <form role="search" aria-label="Search and filter products" onSubmit={handleSearchSubmit}>
        <div className="form-field">
          <label htmlFor="products-search">Search</label>
          <input
            id="products-search"
            type="search"
            value={searchInput}
            onChange={(event) => {
              setSearchInput(event.target.value);
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="products-filter-category">Filter by category</label>
          <select
            id="products-filter-category"
            value={categoryFilter}
            onChange={(event) => {
              setCategoryFilter(event.target.value);
            }}
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="products-filter-type">Filter by type</label>
          <select
            id="products-filter-type"
            value={typeFilter}
            onChange={(event) => {
              setTypeFilter(event.target.value as ProductType | '');
            }}
          >
            <option value="">All types</option>
            {(Object.keys(TYPE_LABELS) as ProductType[]).map((type) => (
              <option key={type} value={type}>
                {TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="button">
          Search
        </button>
      </form>

      <form className="auth-form" onSubmit={handleCreate} aria-label="Create product">
        <h3>Create product</h3>
        <div className="form-field">
          <label htmlFor="product-part-number">Part number</label>
          <input
            id="product-part-number"
            required
            value={form.partNumber}
            onChange={(event) => {
              setForm((current) => ({ ...current, partNumber: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="product-description">Description</label>
          <input
            id="product-description"
            required
            value={form.description}
            onChange={(event) => {
              setForm((current) => ({ ...current, description: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="product-revision">Revision</label>
          <input
            id="product-revision"
            value={form.revision}
            onChange={(event) => {
              setForm((current) => ({ ...current, revision: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="product-category">Category</label>
          <select
            id="product-category"
            value={form.categoryId}
            onChange={(event) => {
              setForm((current) => ({ ...current, categoryId: event.target.value }));
            }}
          >
            <option value="">No category</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="product-type">Type</label>
          <select
            id="product-type"
            value={form.type}
            onChange={(event) => {
              setForm((current) => ({ ...current, type: event.target.value as ProductType }));
            }}
          >
            {(Object.keys(TYPE_LABELS) as ProductType[]).map((type) => (
              <option key={type} value={type}>
                {TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="product-manufacturing-notes">Manufacturing notes</label>
          <textarea
            id="product-manufacturing-notes"
            value={form.manufacturingNotes}
            onChange={(event) => {
              setForm((current) => ({ ...current, manufacturingNotes: event.target.value }));
            }}
          />
        </div>
        <button type="submit" className="button button--primary" disabled={creating}>
          {creating ? 'Creating…' : 'Create product'}
        </button>
      </form>

      {loading && (
        <p role="status" className="auth-loading">
          Loading…
        </p>
      )}
      {loadError && (
        <p role="alert" className="auth-form__error">
          {loadError}
        </p>
      )}

      {!loading && !loadError && products.length === 0 && <p>No products yet.</p>}

      {!loading && !loadError && products.length > 0 && (
        <>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Part number</th>
                  <th scope="col">Description</th>
                  <th scope="col">Revision</th>
                  <th scope="col">Category</th>
                  <th scope="col">Type</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => (
                  <tr key={product.id}>
                    <td>
                      <Link to={`/products/${product.id}`}>{product.part_number}</Link>
                    </td>
                    <td>{product.description}</td>
                    <td>{product.revision}</td>
                    <td>
                      {product.category_id
                        ? (categoryNameById.get(product.category_id) ?? product.category_id)
                        : ''}
                    </td>
                    <td>{TYPE_LABELS[product.type]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="app-header__actions">
            <button
              type="button"
              className="button"
              disabled={!canGoPrevious}
              onClick={() => {
                void loadPage(Math.max(0, offset - pageSize));
              }}
            >
              Previous
            </button>
            <button
              type="button"
              className="button"
              disabled={!canGoNext}
              onClick={() => {
                void loadPage(offset + pageSize);
              }}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
