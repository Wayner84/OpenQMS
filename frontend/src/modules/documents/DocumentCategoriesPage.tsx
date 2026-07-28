import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import {
  createCategory,
  createTag,
  deleteCategory,
  deleteTag,
  listCategories,
  listTags,
  updateCategory,
} from './api';
import type { Category, Tag } from './types';

interface CategoryForm {
  name: string;
  parentCategoryId: string;
}

const emptyCategoryForm: CategoryForm = { name: '', parentCategoryId: '' };

function toForm(category: Category): CategoryForm {
  return { name: category.name, parentCategoryId: category.parent_category_id ?? '' };
}

/** Every id transitively reachable as a child of `rootId` -- offering one of
 * these as a parent choice for `rootId` itself would create a cycle, which the
 * backend also rejects (422), but excluding them here avoids a round trip for a
 * choice that could never succeed. */
function descendantIds(categories: Category[], rootId: string): ReadonlySet<string> {
  const childrenByParent = new Map<string, string[]>();
  for (const category of categories) {
    if (category.parent_category_id) {
      const siblings = childrenByParent.get(category.parent_category_id) ?? [];
      siblings.push(category.id);
      childrenByParent.set(category.parent_category_id, siblings);
    }
  }
  const result = new Set<string>();
  const queue = [...(childrenByParent.get(rootId) ?? [])];
  while (queue.length > 0) {
    const id = queue.pop();
    if (id === undefined || result.has(id)) {
      continue;
    }
    result.add(id);
    queue.push(...(childrenByParent.get(id) ?? []));
  }
  return result;
}

/**
 * Admin-only document category tree and tag administration. Reachable from
 * {@link DocumentsPage}; gated by `<ProtectedRoute requireAdmin>` in App.tsx, not by
 * this component itself (matching UsersPage's pattern) -- every mutation is still
 * independently re-enforced server-side regardless.
 */
export function DocumentCategoriesPage(): ReactElement {
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [tagError, setTagError] = useState<string | null>(null);
  const [pendingCategoryIds, setPendingCategoryIds] = useState<ReadonlySet<string>>(new Set());
  const [pendingTagIds, setPendingTagIds] = useState<ReadonlySet<string>>(new Set());
  const [categoryForm, setCategoryForm] = useState<CategoryForm>(emptyCategoryForm);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [savingCategory, setSavingCategory] = useState(false);
  const [tagName, setTagName] = useState('');
  const [savingTag, setSavingTag] = useState(false);
  const mountedRef = useRef(true);
  const loadRequestIdRef = useRef(0);

  const excludedParentIds = useMemo(
    () =>
      editingCategoryId
        ? new Set([editingCategoryId, ...descendantIds(categories, editingCategoryId)])
        : new Set<string>(),
    [categories, editingCategoryId],
  );

  useEffect(() => {
    // Set (not just read) on every (re-)mount, not only cleared on unmount: React 18
    // StrictMode double-invokes this effect in development (mount, cleanup, mount
    // again) to surface missing-cleanup bugs. Without resetting to `true` here, the
    // cleanup from that simulated first mount leaves this permanently `false`, so
    // every subsequent `if (mountedRef.current) setState(...)` below silently no-ops
    // — including the ones that turn off the initial loading state.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadAll = useCallback(async () => {
    // A later call to `loadAll` (React StrictMode's simulated double-invoke on
    // mount, or a refresh triggered by an action while a previous load was still
    // in flight) must win even if its response arrives first -- an out-of-order
    // response from an *earlier* call must never overwrite state a *later* call
    // already set. Guarding on a monotonically increasing request id (not just
    // `mountedRef`, which only covers unmount) makes that ordering explicit
    // rather than assuming responses arrive in call order.
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    setLoadError(null);
    try {
      const [categoryItems, tagItems] = await Promise.all([
        fetchAllPages<Category>((params) => listCategories(params)),
        fetchAllPages<Tag>((params) => listTags(params)),
      ]);
      if (mountedRef.current && loadRequestIdRef.current === requestId) {
        setCategories(categoryItems);
        setTags(tagItems);
      }
    } catch {
      if (mountedRef.current && loadRequestIdRef.current === requestId) {
        setLoadError('Could not load categories and tags. Please try again.');
      }
    } finally {
      if (mountedRef.current && loadRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const startEditCategory = (category: Category): void => {
    setCategoryError(null);
    setEditingCategoryId(category.id);
    setCategoryForm(toForm(category));
  };

  const cancelEditCategory = (): void => {
    setEditingCategoryId(null);
    setCategoryForm(emptyCategoryForm);
  };

  const handleCategorySubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setCategoryError(null);
    setSavingCategory(true);
    const payload = {
      name: categoryForm.name,
      parent_category_id: categoryForm.parentCategoryId || undefined,
    };
    void (async () => {
      try {
        if (editingCategoryId) {
          await updateCategory(editingCategoryId, payload);
        } else {
          await createCategory(payload);
        }
        if (mountedRef.current) {
          setCategoryForm(emptyCategoryForm);
          setEditingCategoryId(null);
        }
        await loadAll();
      } catch (err) {
        if (mountedRef.current) {
          setCategoryError(
            getErrorDetail(err) ??
              `Could not ${editingCategoryId ? 'update' : 'create'} the category. Please try again.`,
          );
        }
      } finally {
        if (mountedRef.current) {
          setSavingCategory(false);
        }
      }
    })();
  };

  const handleDeleteCategory = (category: Category): void => {
    if (!window.confirm(`Delete the category "${category.name}"?`)) {
      return;
    }
    setCategoryError(null);
    setPendingCategoryIds((current) => new Set(current).add(category.id));
    void (async () => {
      try {
        await deleteCategory(category.id);
        await loadAll();
      } catch (err) {
        if (mountedRef.current) {
          setCategoryError(
            getErrorDetail(err) ?? 'Could not delete the category. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current) {
          setPendingCategoryIds((current) => {
            const next = new Set(current);
            next.delete(category.id);
            return next;
          });
        }
      }
    })();
  };

  const handleTagSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setTagError(null);
    setSavingTag(true);
    void (async () => {
      try {
        await createTag({ name: tagName });
        if (mountedRef.current) {
          setTagName('');
        }
        await loadAll();
      } catch (err) {
        if (mountedRef.current) {
          setTagError(getErrorDetail(err) ?? 'Could not create the tag. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setSavingTag(false);
        }
      }
    })();
  };

  const handleDeleteTag = (tag: Tag): void => {
    if (!window.confirm(`Delete the tag "${tag.name}"?`)) {
      return;
    }
    setTagError(null);
    setPendingTagIds((current) => new Set(current).add(tag.id));
    void (async () => {
      try {
        await deleteTag(tag.id);
        await loadAll();
      } catch (err) {
        if (mountedRef.current) {
          setTagError(getErrorDetail(err) ?? 'Could not delete the tag. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setPendingTagIds((current) => {
            const next = new Set(current);
            next.delete(tag.id);
            return next;
          });
        }
      }
    })();
  };

  return (
    <section>
      <h2>Document categories &amp; tags</h2>

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
          <section>
            <h3>Categories</h3>
            {categoryError && (
              <p role="alert" className="auth-form__error">
                {categoryError}
              </p>
            )}
            <form
              className="auth-form"
              onSubmit={handleCategorySubmit}
              aria-label={editingCategoryId ? 'Edit category' : 'Create category'}
            >
              <div className="form-field">
                <label htmlFor="category-name">Category name</label>
                <input
                  id="category-name"
                  required
                  value={categoryForm.name}
                  onChange={(event) => {
                    setCategoryForm((current) => ({ ...current, name: event.target.value }));
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="category-parent">Parent category</label>
                <select
                  id="category-parent"
                  value={categoryForm.parentCategoryId}
                  onChange={(event) => {
                    setCategoryForm((current) => ({
                      ...current,
                      parentCategoryId: event.target.value,
                    }));
                  }}
                >
                  <option value="">No parent (top level)</option>
                  {categories
                    .filter((category) => !excludedParentIds.has(category.id))
                    .map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                </select>
              </div>
              <button type="submit" className="button button--primary" disabled={savingCategory}>
                {savingCategory
                  ? 'Saving…'
                  : editingCategoryId
                    ? 'Save changes'
                    : 'Create category'}
              </button>
              {editingCategoryId && (
                <button type="button" className="button" onClick={cancelEditCategory}>
                  Cancel
                </button>
              )}
            </form>

            {categories.length === 0 ? (
              <p>No categories yet.</p>
            ) : (
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Name</th>
                      <th scope="col">Parent</th>
                      <th scope="col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.map((category) => {
                      const isPending = pendingCategoryIds.has(category.id);
                      const parentName = category.parent_category_id
                        ? (categories.find((c) => c.id === category.parent_category_id)?.name ??
                          category.parent_category_id)
                        : '';
                      return (
                        <tr key={category.id}>
                          <td>{category.name}</td>
                          <td>{parentName}</td>
                          <td>
                            <button
                              type="button"
                              className="button"
                              disabled={isPending}
                              onClick={() => {
                                startEditCategory(category);
                              }}
                            >
                              Edit {category.name}
                            </button>{' '}
                            <button
                              type="button"
                              className="button"
                              disabled={isPending}
                              onClick={() => {
                                handleDeleteCategory(category);
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
            )}
          </section>

          <section>
            <h3>Tags</h3>
            {tagError && (
              <p role="alert" className="auth-form__error">
                {tagError}
              </p>
            )}
            <form className="auth-form" onSubmit={handleTagSubmit} aria-label="Create tag">
              <div className="form-field">
                <label htmlFor="tag-name">Tag name</label>
                <input
                  id="tag-name"
                  required
                  value={tagName}
                  onChange={(event) => {
                    setTagName(event.target.value);
                  }}
                />
              </div>
              <button type="submit" className="button button--primary" disabled={savingTag}>
                {savingTag ? 'Creating…' : 'Create tag'}
              </button>
            </form>

            {tags.length === 0 ? (
              <p>No tags yet.</p>
            ) : (
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Name</th>
                      <th scope="col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tags.map((tag) => {
                      const isPending = pendingTagIds.has(tag.id);
                      return (
                        <tr key={tag.id}>
                          <td>{tag.name}</td>
                          <td>
                            <button
                              type="button"
                              className="button"
                              disabled={isPending}
                              onClick={() => {
                                handleDeleteTag(tag);
                              }}
                            >
                              Delete {tag.name}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
