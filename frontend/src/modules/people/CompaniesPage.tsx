import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { createCompany, deleteCompany, listCompanies, updateCompany } from './api';
import type { Company, CompanyType } from './types';

const DEFAULT_PAGE_SIZE = 20;

interface CompanyForm {
  name: string;
  type: CompanyType;
  address: string;
  phone: string;
  general_email: string;
  notes: string;
}

const emptyForm: CompanyForm = {
  name: '',
  type: 'other',
  address: '',
  phone: '',
  general_email: '',
  notes: '',
};

function toForm(company: Company): CompanyForm {
  return {
    name: company.name,
    type: company.type,
    address: company.address ?? '',
    phone: company.phone ?? '',
    general_email: company.general_email ?? '',
    notes: company.notes ?? '',
  };
}

/** The company (customer/supplier/other) directory: create, list (paginated), edit, and delete. */
export function CompaniesPage({
  pageSize = DEFAULT_PAGE_SIZE,
}: {
  pageSize?: number;
}): ReactElement {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<ReadonlySet<string>>(new Set());
  const [form, setForm] = useState<CompanyForm>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mountedRef = useRef(true);

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

  const loadPage = useCallback(
    async (nextOffset: number) => {
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listCompanies({ limit: pageSize, offset: nextOffset });
        if (mountedRef.current) {
          setCompanies(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current) {
          setLoadError('Could not load companies. Please try again.');
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

  const startEdit = (company: Company): void => {
    setActionError(null);
    setEditingId(company.id);
    setForm(toForm(company));
  };

  const cancelEdit = (): void => {
    setEditingId(null);
    setForm(emptyForm);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setActionError(null);
    setSubmitting(true);
    const payload = {
      name: form.name,
      type: form.type,
      address: form.address || undefined,
      phone: form.phone || undefined,
      general_email: form.general_email || undefined,
      notes: form.notes || undefined,
    };
    void (async () => {
      try {
        if (editingId) {
          await updateCompany(editingId, payload);
        } else {
          await createCompany(payload);
        }
        if (mountedRef.current) {
          setForm(emptyForm);
          setEditingId(null);
        }
        await loadPage(editingId ? offset : 0);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(
            getErrorDetail(err) ??
              `Could not ${editingId ? 'update' : 'create'} the company. Please try again.`,
          );
        }
      } finally {
        if (mountedRef.current) {
          setSubmitting(false);
        }
      }
    })();
  };

  const handleDelete = (company: Company): void => {
    setActionError(null);
    setPendingIds((current) => new Set(current).add(company.id));
    void (async () => {
      try {
        await deleteCompany(company.id);
        await loadPage(offset);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not delete the company. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setPendingIds((current) => {
            const next = new Set(current);
            next.delete(company.id);
            return next;
          });
        }
      }
    })();
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + companies.length < total;

  return (
    <section>
      <h2>Companies</h2>
      {actionError && (
        <p role="alert" className="auth-form__error">
          {actionError}
        </p>
      )}

      <form
        className="auth-form"
        onSubmit={handleSubmit}
        aria-label={editingId ? 'Edit company' : 'Create company'}
      >
        <h3>{editingId ? 'Edit company' : 'Create company'}</h3>
        <div className="form-field">
          <label htmlFor="company-name">Name</label>
          <input
            id="company-name"
            required
            value={form.name}
            onChange={(event) => {
              setForm((current) => ({ ...current, name: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="company-type">Type</label>
          <select
            id="company-type"
            value={form.type}
            onChange={(event) => {
              setForm((current) => ({ ...current, type: event.target.value as CompanyType }));
            }}
          >
            <option value="customer">Customer</option>
            <option value="supplier">Supplier</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="company-address">Address</label>
          <input
            id="company-address"
            value={form.address}
            onChange={(event) => {
              setForm((current) => ({ ...current, address: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="company-phone">Phone</label>
          <input
            id="company-phone"
            value={form.phone}
            onChange={(event) => {
              setForm((current) => ({ ...current, phone: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="company-email">General email</label>
          <input
            id="company-email"
            type="email"
            value={form.general_email}
            onChange={(event) => {
              setForm((current) => ({ ...current, general_email: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="company-notes">Notes</label>
          <textarea
            id="company-notes"
            value={form.notes}
            onChange={(event) => {
              setForm((current) => ({ ...current, notes: event.target.value }));
            }}
          />
        </div>
        <button type="submit" className="button button--primary" disabled={submitting}>
          {submitting ? 'Saving…' : editingId ? 'Save changes' : 'Create company'}
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
                  <th scope="col">Type</th>
                  <th scope="col">Phone</th>
                  <th scope="col">Email</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => {
                  const isPending = pendingIds.has(company.id);
                  return (
                    <tr key={company.id}>
                      <td>{company.name}</td>
                      <td>{company.type}</td>
                      <td>{company.phone}</td>
                      <td>{company.general_email}</td>
                      <td>
                        <Link to={`/people?company=${company.id}`}>
                          View contacts for {company.name}
                        </Link>{' '}
                        <button
                          type="button"
                          className="button"
                          disabled={isPending}
                          onClick={() => {
                            startEdit(company);
                          }}
                        >
                          Edit {company.name}
                        </button>{' '}
                        <button
                          type="button"
                          className="button"
                          disabled={isPending}
                          onClick={() => {
                            handleDelete(company);
                          }}
                        >
                          Delete {company.name}
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
