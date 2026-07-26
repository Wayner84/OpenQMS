import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { createPerson, deletePerson, listCompanies, listPeople, updatePerson } from './api';
import type { Company, Person } from './types';

const DEFAULT_PAGE_SIZE = 20;
const COMPANY_PAGE_SIZE = 200;

interface PersonForm {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: string;
  department: string;
  notes: string;
  is_employee: boolean;
  company_id: string;
}

function emptyForm(companyId?: string | null): PersonForm {
  return {
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    role: '',
    department: '',
    notes: '',
    is_employee: false,
    company_id: companyId ?? '',
  };
}

function toForm(person: Person): PersonForm {
  return {
    first_name: person.first_name,
    last_name: person.last_name,
    email: person.email ?? '',
    phone: person.phone ?? '',
    role: person.role ?? '',
    department: person.department ?? '',
    notes: person.notes ?? '',
    is_employee: person.is_employee,
    company_id: person.company_id ?? '',
  };
}

/**
 * The people directory: employees and per-company contacts. Create/list (paginated,
 * searchable)/edit/delete. A `?company=<id>` query param (set by the "View contacts"
 * link on CompaniesPage) pre-filters the list to one company's contacts.
 */
export function PeoplePage({ pageSize = DEFAULT_PAGE_SIZE }: { pageSize?: number }): ReactElement {
  const [searchParams] = useSearchParams();
  const companyFilter = searchParams.get('company');

  const [people, setPeople] = useState<Person[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<ReadonlySet<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [form, setForm] = useState<PersonForm>(() => emptyForm(companyFilter));
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mountedRef = useRef(true);

  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  useEffect(() => {
    void listCompanies({ limit: COMPANY_PAGE_SIZE }).then((page) => {
      if (mountedRef.current) {
        setCompanies(page.items);
      }
    });
  }, []);

  useEffect(() => {
    setEditingId(null);
    setForm(emptyForm(companyFilter));
  }, [companyFilter]);

  const companyNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const company of companies) {
      map.set(company.id, company.name);
    }
    return map;
  }, [companies]);

  const loadPage = useCallback(
    async (nextOffset: number, search: string) => {
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listPeople({
          limit: pageSize,
          offset: nextOffset,
          search: search || undefined,
          companyId: companyFilter ?? undefined,
        });
        if (mountedRef.current) {
          setPeople(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current) {
          setLoadError('Could not load people. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [pageSize, companyFilter],
  );

  useEffect(() => {
    void loadPage(0, searchTerm);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- searchTerm changes are applied via handleSearchSubmit, not on every keystroke
  }, [loadPage]);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setSearchTerm(searchInput);
    void loadPage(0, searchInput);
  };

  const startEdit = (person: Person): void => {
    setActionError(null);
    setEditingId(person.id);
    setForm(toForm(person));
  };

  const cancelEdit = (): void => {
    setEditingId(null);
    setForm(emptyForm(companyFilter));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setActionError(null);
    setSubmitting(true);
    const payload = {
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email || undefined,
      phone: form.phone || undefined,
      role: form.role || undefined,
      department: form.department || undefined,
      notes: form.notes || undefined,
      is_employee: form.is_employee,
      company_id: form.is_employee ? null : form.company_id || null,
    };
    void (async () => {
      try {
        if (editingId) {
          await updatePerson(editingId, payload);
        } else {
          await createPerson(payload);
        }
        if (mountedRef.current) {
          setForm(emptyForm(companyFilter));
          setEditingId(null);
        }
        await loadPage(editingId ? offset : 0, searchTerm);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(
            getErrorDetail(err) ??
              `Could not ${editingId ? 'update' : 'create'} the person. Please try again.`,
          );
        }
      } finally {
        if (mountedRef.current) {
          setSubmitting(false);
        }
      }
    })();
  };

  const handleDelete = (person: Person): void => {
    setActionError(null);
    setPendingIds((current) => new Set(current).add(person.id));
    void (async () => {
      try {
        await deletePerson(person.id);
        await loadPage(offset, searchTerm);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not delete the person. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setPendingIds((current) => {
            const next = new Set(current);
            next.delete(person.id);
            return next;
          });
        }
      }
    })();
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + people.length < total;
  const filteredCompanyName = companyFilter ? companyNameById.get(companyFilter) : undefined;

  return (
    <section>
      <h2>People</h2>
      {companyFilter && (
        <p className="auth-loading">
          Showing contacts for {filteredCompanyName ?? companyFilter}.{' '}
          <Link to="/people">Show everyone</Link>
        </p>
      )}
      {actionError && (
        <p role="alert" className="auth-form__error">
          {actionError}
        </p>
      )}

      <form role="search" aria-label="Search people" onSubmit={handleSearchSubmit}>
        <label htmlFor="people-search" className="visually-hidden">
          Search people
        </label>
        <input
          id="people-search"
          type="search"
          value={searchInput}
          onChange={(event) => {
            setSearchInput(event.target.value);
          }}
        />
        <button type="submit" className="button">
          Search
        </button>
      </form>

      <form
        className="auth-form"
        onSubmit={handleSubmit}
        aria-label={editingId ? 'Edit person' : 'Create person'}
      >
        <h3>{editingId ? 'Edit person' : 'Create person'}</h3>
        <div className="form-field">
          <label htmlFor="person-first-name">First name</label>
          <input
            id="person-first-name"
            required
            value={form.first_name}
            onChange={(event) => {
              setForm((current) => ({ ...current, first_name: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="person-last-name">Last name</label>
          <input
            id="person-last-name"
            required
            value={form.last_name}
            onChange={(event) => {
              setForm((current) => ({ ...current, last_name: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="person-email">Email</label>
          <input
            id="person-email"
            type="email"
            value={form.email}
            onChange={(event) => {
              setForm((current) => ({ ...current, email: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="person-phone">Phone</label>
          <input
            id="person-phone"
            value={form.phone}
            onChange={(event) => {
              setForm((current) => ({ ...current, phone: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="person-role">Role</label>
          <input
            id="person-role"
            value={form.role}
            onChange={(event) => {
              setForm((current) => ({ ...current, role: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="person-department">Department</label>
          <input
            id="person-department"
            value={form.department}
            onChange={(event) => {
              setForm((current) => ({ ...current, department: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="person-notes">Notes</label>
          <textarea
            id="person-notes"
            value={form.notes}
            onChange={(event) => {
              setForm((current) => ({ ...current, notes: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="person-employee">
            <input
              id="person-employee"
              type="checkbox"
              checked={form.is_employee}
              onChange={(event) => {
                setForm((current) => ({ ...current, is_employee: event.target.checked }));
              }}
            />{' '}
            Is an employee
          </label>
        </div>
        {!form.is_employee && (
          <div className="form-field">
            <label htmlFor="person-company">Company</label>
            <select
              id="person-company"
              required
              value={form.company_id}
              onChange={(event) => {
                setForm((current) => ({ ...current, company_id: event.target.value }));
              }}
            >
              <option value="">Select a company…</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <button type="submit" className="button button--primary" disabled={submitting}>
          {submitting ? 'Saving…' : editingId ? 'Save changes' : 'Create person'}
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
                  <th scope="col">Email</th>
                  <th scope="col">Phone</th>
                  <th scope="col">Role</th>
                  <th scope="col">Department</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {people.map((person) => {
                  const isPending = pendingIds.has(person.id);
                  const fullName = `${person.first_name} ${person.last_name}`;
                  return (
                    <tr key={person.id}>
                      <td>{fullName}</td>
                      <td>
                        {person.is_employee
                          ? 'Employee'
                          : `Contact — ${
                              person.company_id
                                ? (companyNameById.get(person.company_id) ?? person.company_id)
                                : ''
                            }`}
                      </td>
                      <td>{person.email}</td>
                      <td>{person.phone}</td>
                      <td>{person.role}</td>
                      <td>{person.department}</td>
                      <td>
                        <button
                          type="button"
                          className="button"
                          disabled={isPending}
                          onClick={() => {
                            startEdit(person);
                          }}
                        >
                          Edit {fullName}
                        </button>{' '}
                        <button
                          type="button"
                          className="button"
                          disabled={isPending}
                          onClick={() => {
                            handleDelete(person);
                          }}
                        >
                          Delete {fullName}
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
                void loadPage(Math.max(0, offset - pageSize), searchTerm);
              }}
            >
              Previous
            </button>
            <button
              type="button"
              className="button"
              disabled={!canGoNext}
              onClick={() => {
                void loadPage(offset + pageSize, searchTerm);
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
