import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { listCompanies, listPeople } from '../people/api';
import type { Company, Person } from '../people/types';
import { listProducts } from '../products/api';
import type { Product } from '../products/types';
import { listSuppliers } from '../suppliers/api';
import type { Supplier } from '../suppliers/types';
import { createNcr, listNcrs } from './api';
import type { Ncr, NcrStatus, NcrType } from './types';

const DEFAULT_PAGE_SIZE = 20;

const TYPE_LABELS: Record<NcrType, string> = {
  internal: 'Internal',
  supplier: 'Supplier',
};

const STATUS_LABELS: Record<NcrStatus, string> = {
  open: 'Open',
  investigate: 'Investigate',
  containment: 'Containment',
  corrective_action: 'Corrective action',
  verification: 'Verification',
  closed: 'Closed',
};

interface CreateForm {
  type: NcrType;
  productId: string;
  supplierId: string;
  raisedById: string;
  description: string;
}

const emptyForm: CreateForm = {
  type: 'internal',
  productId: '',
  supplierId: '',
  raisedById: '',
  description: '',
};

function personDisplayName(person: Person): string {
  return `${person.first_name} ${person.last_name}`;
}

/**
 * The NCR register: searchable/filterable list (any active user, per the
 * Milestone 4 plan's design decision 2) and a create form. `supplier_id` is only
 * shown/required when `type` is `supplier`, mirroring the backend's
 * type/supplier_id invariant (design decision 5).
 */
export function NcrsPage({ pageSize = DEFAULT_PAGE_SIZE }: { pageSize?: number }): ReactElement {
  const [ncrs, setNcrs] = useState<Ncr[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState<NcrType | ''>('');
  const [statusFilter, setStatusFilter] = useState<NcrStatus | ''>('');
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
    void Promise.all([
      fetchAllPages<Product>((params) => listProducts(params)),
      fetchAllPages<Supplier>((params) => listSuppliers(params)),
      fetchAllPages<Company>((params) => listCompanies(params)),
      fetchAllPages<Person>((params) => listPeople(params)),
    ])
      .then(([productItems, supplierItems, companyItems, personItems]) => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setProducts(productItems);
          setSuppliers(supplierItems);
          setCompanies(companyItems);
          setPeople(personItems);
        }
      })
      .catch(() => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setOptionsError('Could not load products, suppliers, or people. Please try again.');
        }
      });
  }, [refreshVersion]);

  const companyNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const company of companies) {
      map.set(company.id, company.name);
    }
    return map;
  }, [companies]);

  const supplierLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const supplier of suppliers) {
      map.set(supplier.id, companyNameById.get(supplier.company_id) ?? supplier.company_id);
    }
    return map;
  }, [suppliers, companyNameById]);

  const loadPage = useCallback(
    async (nextOffset: number) => {
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listNcrs({
          limit: pageSize,
          offset: nextOffset,
          search: searchTerm || undefined,
          type: typeFilter || undefined,
          status: statusFilter || undefined,
        });
        if (mountedRef.current && requestIdRef.current === requestId) {
          setNcrs(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoadError('Could not load NCRs. Please try again.');
        }
      } finally {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoading(false);
        }
      }
    },
    [pageSize, searchTerm, typeFilter, statusFilter],
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
        await createNcr({
          type: form.type,
          product_id: form.productId || undefined,
          supplier_id: form.type === 'supplier' ? form.supplierId || undefined : undefined,
          raised_by_id: form.raisedById,
          description: form.description,
        });
        if (mountedRef.current) {
          setForm(emptyForm);
        }
        setRefreshVersion((current) => current + 1);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not create the NCR. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setCreating(false);
        }
      }
    })();
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + ncrs.length < total;

  return (
    <section>
      <h2>NCR</h2>
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

      <form role="search" aria-label="Search and filter NCRs" onSubmit={handleSearchSubmit}>
        <div className="form-field">
          <label htmlFor="ncr-search">Search</label>
          <input
            id="ncr-search"
            type="search"
            value={searchInput}
            onChange={(event) => {
              setSearchInput(event.target.value);
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="ncr-filter-type">Filter by type</label>
          <select
            id="ncr-filter-type"
            value={typeFilter}
            onChange={(event) => {
              setTypeFilter(event.target.value as NcrType | '');
            }}
          >
            <option value="">All types</option>
            {(Object.keys(TYPE_LABELS) as NcrType[]).map((type) => (
              <option key={type} value={type}>
                {TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="ncr-filter-status">Filter by status</label>
          <select
            id="ncr-filter-status"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value as NcrStatus | '');
            }}
          >
            <option value="">All statuses</option>
            {(Object.keys(STATUS_LABELS) as NcrStatus[]).map((status) => (
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

      <form className="auth-form" onSubmit={handleCreate} aria-label="Create NCR">
        <h3>Create NCR</h3>
        <div className="form-field">
          <label htmlFor="ncr-type">Type</label>
          <select
            id="ncr-type"
            value={form.type}
            onChange={(event) => {
              setForm((current) => ({
                ...current,
                type: event.target.value as NcrType,
                supplierId: '',
              }));
            }}
          >
            {(Object.keys(TYPE_LABELS) as NcrType[]).map((type) => (
              <option key={type} value={type}>
                {TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="ncr-raised-by">Raised by</label>
          <select
            id="ncr-raised-by"
            required
            value={form.raisedById}
            onChange={(event) => {
              setForm((current) => ({ ...current, raisedById: event.target.value }));
            }}
          >
            <option value="">Choose a person</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {personDisplayName(person)}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="ncr-product">Product (optional)</label>
          <select
            id="ncr-product"
            value={form.productId}
            onChange={(event) => {
              setForm((current) => ({ ...current, productId: event.target.value }));
            }}
          >
            <option value="">No product</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.part_number} — {product.description}
              </option>
            ))}
          </select>
        </div>
        {form.type === 'supplier' && (
          <div className="form-field">
            <label htmlFor="ncr-supplier">Supplier</label>
            <select
              id="ncr-supplier"
              required
              value={form.supplierId}
              onChange={(event) => {
                setForm((current) => ({ ...current, supplierId: event.target.value }));
              }}
            >
              <option value="">Choose a supplier</option>
              {suppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplierLabelById.get(supplier.id) ?? supplier.id}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="form-field">
          <label htmlFor="ncr-description">Description</label>
          <textarea
            id="ncr-description"
            required
            value={form.description}
            onChange={(event) => {
              setForm((current) => ({ ...current, description: event.target.value }));
            }}
          />
        </div>
        <button type="submit" className="button button--primary" disabled={creating}>
          {creating ? 'Creating…' : 'Create NCR'}
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

      {!loading && !loadError && ncrs.length === 0 && <p>No NCRs yet.</p>}

      {!loading && !loadError && ncrs.length > 0 && (
        <>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Number</th>
                  <th scope="col">Type</th>
                  <th scope="col">Status</th>
                  <th scope="col">Description</th>
                </tr>
              </thead>
              <tbody>
                {ncrs.map((ncr) => (
                  <tr key={ncr.id}>
                    <td>
                      <Link to={`/ncr/${ncr.id}`}>{ncr.number}</Link>
                    </td>
                    <td>{TYPE_LABELS[ncr.type]}</td>
                    <td>{STATUS_LABELS[ncr.status]}</td>
                    <td>{ncr.description}</td>
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
