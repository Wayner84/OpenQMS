import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';

import { getErrorDetail } from '../../shared/api/client';
import {
  createProductCategory,
  deleteProductCategory,
  listProductCategories,
  updateProductCategory,
} from './api';
import type { ProductCategory } from './types';

const DEFAULT_PAGE_SIZE = 50;

/**
 * Flat product category administration: create/list/edit/delete, reachable from
 * {@link ProductsPage}. Not admin-gated -- see the Milestone 3 plan's design
 * decision 2 (Products/Suppliers are collaborative reference data, unlike Document
 * Management's admin-gated categories).
 */
export function ProductCategoriesPage({
  pageSize = DEFAULT_PAGE_SIZE,
}: {
  pageSize?: number;
}): ReactElement {
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<ReadonlySet<string>>(new Set());
  const [name, setName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadPage = useCallback(
    async (nextOffset: number) => {
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listProductCategories({ limit: pageSize, offset: nextOffset });
        if (mountedRef.current) {
          setCategories(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current) {
          setLoadError('Could not load product categories. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [pageSize],
  );

  useEffect(() => {
    void loadPage(0);
  }, [loadPage]);

  const startEdit = (category: ProductCategory): void => {
    setActionError(null);
    setEditingId(category.id);
    setName(category.name);
  };

  const cancelEdit = (): void => {
    setEditingId(null);
    setName('');
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setActionError(null);
    setSubmitting(true);
    void (async () => {
      try {
        if (editingId) {
          await updateProductCategory(editingId, { name });
        } else {
          await createProductCategory({ name });
        }
        if (mountedRef.current) {
          setName('');
          setEditingId(null);
        }
        await loadPage(editingId ? offset : 0);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(
            getErrorDetail(err) ??
              `Could not ${editingId ? 'update' : 'create'} the category. Please try again.`,
          );
        }
      } finally {
        if (mountedRef.current) {
          setSubmitting(false);
        }
      }
    })();
  };

  const handleDelete = (category: ProductCategory): void => {
    setActionError(null);
    setPendingIds((current) => new Set(current).add(category.id));
    void (async () => {
      try {
        await deleteProductCategory(category.id);
        await loadPage(offset);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not delete the category. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setPendingIds((current) => {
            const next = new Set(current);
            next.delete(category.id);
            return next;
          });
        }
      }
    })();
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + categories.length < total;

  return (
    <section>
      <h2>Product categories</h2>
      {actionError && (
        <p role="alert" className="auth-form__error">
          {actionError}
        </p>
      )}

      <form
        className="auth-form"
        onSubmit={handleSubmit}
        aria-label={editingId ? 'Edit category' : 'Create category'}
      >
        <h3>{editingId ? 'Edit category' : 'Create category'}</h3>
        <div className="form-field">
          <label htmlFor="category-name">Name</label>
          <input
            id="category-name"
            required
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </div>
        <button type="submit" className="button button--primary" disabled={submitting}>
          {submitting ? 'Saving…' : editingId ? 'Save changes' : 'Create category'}
        </button>
        {editingId && (
          <button type="button" className="button" onClick={cancelEdit}>
            Cancel
          </button>
        )}
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

      {!loading && !loadError && (
        <>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((category) => {
                  const isPending = pendingIds.has(category.id);
                  return (
                    <tr key={category.id}>
                      <td>{category.name}</td>
                      <td>
                        <button
                          type="button"
                          className="button"
                          disabled={isPending}
                          onClick={() => {
                            startEdit(category);
                          }}
                        >
                          Edit {category.name}
                        </button>{' '}
                        <button
                          type="button"
                          className="button"
                          disabled={isPending}
                          onClick={() => {
                            handleDelete(category);
                          }}
                        >
                          Delete {category.name}
                        </button>
                      </td>
                    </tr>
                  );
                })}
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
