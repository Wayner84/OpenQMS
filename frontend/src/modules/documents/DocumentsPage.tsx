import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { useAuth } from '../auth/AuthContext';
import { listPeople } from '../people/api';
import type { Person } from '../people/types';
import { createDocument, listCategories, listDocuments, listTags } from './api';
import type { Category, DocumentRecord, DocumentStatus, Tag } from './types';

const DEFAULT_PAGE_SIZE = 20;

function personDisplayName(person: Person): string {
  return `${person.first_name} ${person.last_name}`;
}

const STATUS_LABELS: Record<DocumentStatus, string> = {
  draft: 'Draft',
  in_review: 'In review',
  approved: 'Approved',
  obsolete: 'Obsolete',
};

interface CreateForm {
  title: string;
  categoryId: string;
  tagIds: string[];
}

const emptyForm: CreateForm = { title: '', categoryId: '', tagIds: [] };

/**
 * The document register: searchable/filterable list (any active user) and a
 * create-document form. Category/tag administration lives on
 * {@link DocumentCategoriesPage} (admin only), linked from here.
 */
export function DocumentsPage({
  pageSize = DEFAULT_PAGE_SIZE,
}: {
  pageSize?: number;
}): ReactElement {
  const { user } = useAuth();

  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [owners, setOwners] = useState<Person[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [ownerFilter, setOwnerFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | ''>('');
  const [form, setForm] = useState<CreateForm>(emptyForm);
  const [creating, setCreating] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);
  const optionsRequestIdRef = useRef(0);

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

  useEffect(() => {
    const requestId = ++optionsRequestIdRef.current;
    setOptionsError(null);
    void Promise.all([
      fetchAllPages<Category>((params) => listCategories(params)),
      fetchAllPages<Tag>((params) => listTags(params)),
      fetchAllPages<Person>((params) => listPeople(params)),
    ])
      .then(([categoryItems, tagItems, ownerItems]) => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setCategories(categoryItems);
          setTags(tagItems);
          setOwners(ownerItems);
        }
      })
      .catch(() => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setOptionsError('Could not load categories/tags/owners for filtering. Please try again.');
        }
      });
  }, []);

  const categoryNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const category of categories) {
      map.set(category.id, category.name);
    }
    return map;
  }, [categories]);

  const ownerNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const person of owners) {
      map.set(person.id, personDisplayName(person));
    }
    return map;
  }, [owners]);

  const loadPage = useCallback(
    async (nextOffset: number) => {
      // A later call to `loadPage` (a filter change, or Next/Previous clicked
      // again before the first request lands) must win even if its response
      // arrives first -- an out-of-order response from an *earlier* request must
      // never overwrite state a *later* request has already set. Guarding on a
      // monotonically increasing request id (not just `mountedRef`, which only
      // covers unmount) makes that ordering explicit rather than assuming
      // network responses arrive in request order.
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listDocuments({
          limit: pageSize,
          offset: nextOffset,
          search: searchTerm || undefined,
          categoryId: categoryFilter || undefined,
          tag: tagFilter || undefined,
          ownerId: ownerFilter || undefined,
          status: statusFilter || undefined,
        });
        if (mountedRef.current && requestIdRef.current === requestId) {
          setDocuments(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoadError('Could not load documents. Please try again.');
        }
      } finally {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoading(false);
        }
      }
    },
    [pageSize, searchTerm, categoryFilter, tagFilter, ownerFilter, statusFilter],
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
        await createDocument({
          title: form.title,
          category_id: form.categoryId || undefined,
          tag_ids: form.tagIds,
        });
        if (mountedRef.current) {
          setForm(emptyForm);
        }
        // Trigger the effect above rather than calling the `loadPage` closure
        // captured when creation started. Filters may have changed while the POST
        // was in flight; the next render's callback contains the current filters.
        setRefreshVersion((current) => current + 1);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not create the document. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setCreating(false);
        }
      }
    })();
  };

  const toggleTag = (tagId: string): void => {
    setForm((current) => ({
      ...current,
      tagIds: current.tagIds.includes(tagId)
        ? current.tagIds.filter((id) => id !== tagId)
        : [...current.tagIds, tagId],
    }));
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + documents.length < total;

  return (
    <section>
      <h2>Documents</h2>
      {user?.role === 'admin' && (
        <p>
          <Link to="/documents/categories">Manage categories &amp; tags</Link>
        </p>
      )}
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

      <form role="search" aria-label="Search and filter documents" onSubmit={handleSearchSubmit}>
        <div className="form-field">
          <label htmlFor="documents-search">Search</label>
          <input
            id="documents-search"
            type="search"
            value={searchInput}
            onChange={(event) => {
              setSearchInput(event.target.value);
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="documents-filter-category">Filter by category</label>
          <select
            id="documents-filter-category"
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
          <label htmlFor="documents-filter-tag">Filter by tag</label>
          <select
            id="documents-filter-tag"
            value={tagFilter}
            onChange={(event) => {
              setTagFilter(event.target.value);
            }}
          >
            <option value="">All tags</option>
            {tags.map((tag) => (
              <option key={tag.id} value={tag.name}>
                {tag.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="documents-filter-owner">Filter by owner</label>
          <select
            id="documents-filter-owner"
            value={ownerFilter}
            onChange={(event) => {
              setOwnerFilter(event.target.value);
            }}
          >
            <option value="">All owners</option>
            {owners.map((owner) => (
              <option key={owner.id} value={owner.id}>
                {personDisplayName(owner)}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="documents-filter-status">Filter by status</label>
          <select
            id="documents-filter-status"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value as DocumentStatus | '');
            }}
          >
            <option value="">All statuses</option>
            {(Object.keys(STATUS_LABELS) as DocumentStatus[]).map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="button">
          Search
        </button>
      </form>

      <form className="auth-form" onSubmit={handleCreate} aria-label="Create document">
        <h3>Create document</h3>
        <div className="form-field">
          <label htmlFor="document-title">Title</label>
          <input
            id="document-title"
            required
            value={form.title}
            onChange={(event) => {
              setForm((current) => ({ ...current, title: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="document-category">Category</label>
          <select
            id="document-category"
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
        {tags.length > 0 && (
          <fieldset className="form-field">
            <legend>Tags</legend>
            {tags.map((tag) => (
              <label key={tag.id} htmlFor={`document-tag-${tag.id}`}>
                <input
                  id={`document-tag-${tag.id}`}
                  type="checkbox"
                  checked={form.tagIds.includes(tag.id)}
                  onChange={() => {
                    toggleTag(tag.id);
                  }}
                />{' '}
                {tag.name}
              </label>
            ))}
          </fieldset>
        )}
        <button type="submit" className="button button--primary" disabled={creating}>
          {creating ? 'Creating…' : 'Create document'}
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

      {!loading && !loadError && documents.length === 0 && <p>No documents yet.</p>}

      {!loading && !loadError && documents.length > 0 && (
        <>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Number</th>
                  <th scope="col">Title</th>
                  <th scope="col">Category</th>
                  <th scope="col">Status</th>
                  <th scope="col">Owner</th>
                  <th scope="col">Tags</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.id}>
                    <td>{document.number}</td>
                    <td>
                      <Link to={`/documents/${document.id}`}>{document.title}</Link>
                    </td>
                    <td>
                      {document.category_id
                        ? (categoryNameById.get(document.category_id) ?? document.category_id)
                        : ''}
                    </td>
                    <td>{STATUS_LABELS[document.status]}</td>
                    <td>
                      {document.owner_id
                        ? (ownerNameById.get(document.owner_id) ?? document.owner_id)
                        : ''}
                    </td>
                    <td>{document.tags.map((tag) => tag.name).join(', ')}</td>
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
