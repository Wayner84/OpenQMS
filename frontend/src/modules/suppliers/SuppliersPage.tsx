import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { listCompanies } from '../people/api';
import type { Company } from '../people/types';
import { createSupplier, listSuppliers } from './api';
import type { ApprovalStatus, RiskRating, Supplier } from './types';

const DEFAULT_PAGE_SIZE = 20;

const APPROVAL_STATUS_LABELS: Record<ApprovalStatus, string> = {
  approved: 'Approved',
  pending: 'Pending',
  suspended: 'Suspended',
};

const RISK_RATING_LABELS: Record<RiskRating, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
};

interface CreateForm {
  companyId: string;
  approvalStatus: ApprovalStatus;
  riskRating: RiskRating | '';
  isPreferred: boolean;
  notes: string;
}

const emptyForm: CreateForm = {
  companyId: '',
  approvalStatus: 'pending',
  riskRating: '',
  isPreferred: false,
  notes: '',
};

/**
 * The supplier register: searchable/filterable list (any active user) and a
 * create-supplier form (selecting an existing company, per docs/modules/Suppliers.md).
 */
export function SuppliersPage({
  pageSize = DEFAULT_PAGE_SIZE,
}: {
  pageSize?: number;
}): ReactElement {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [approvalStatusFilter, setApprovalStatusFilter] = useState<ApprovalStatus | ''>('');
  const [riskRatingFilter, setRiskRatingFilter] = useState<RiskRating | ''>('');
  const [preferredFilter, setPreferredFilter] = useState(false);
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
    void fetchAllPages<Company>((params) => listCompanies(params))
      .then((items) => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setCompanies(items);
        }
      })
      .catch(() => {
        if (mountedRef.current && optionsRequestIdRef.current === requestId) {
          setOptionsError('Could not load companies. Please try again.');
        }
      });
  }, []);

  const companyNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const company of companies) {
      map.set(company.id, company.name);
    }
    return map;
  }, [companies]);

  const loadPage = useCallback(
    async (nextOffset: number) => {
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listSuppliers({
          limit: pageSize,
          offset: nextOffset,
          search: searchTerm || undefined,
          approvalStatus: approvalStatusFilter || undefined,
          riskRating: riskRatingFilter || undefined,
          isPreferred: preferredFilter || undefined,
        });
        if (mountedRef.current && requestIdRef.current === requestId) {
          setSuppliers(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoadError('Could not load suppliers. Please try again.');
        }
      } finally {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setLoading(false);
        }
      }
    },
    [pageSize, searchTerm, approvalStatusFilter, riskRatingFilter, preferredFilter],
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
    if (!form.companyId) {
      setActionError('Choose a company for this supplier.');
      return;
    }
    setActionError(null);
    setCreating(true);
    void (async () => {
      try {
        await createSupplier({
          company_id: form.companyId,
          approval_status: form.approvalStatus,
          risk_rating: form.riskRating || undefined,
          is_preferred: form.isPreferred,
          notes: form.notes || undefined,
        });
        if (mountedRef.current) {
          setForm(emptyForm);
        }
        setRefreshVersion((current) => current + 1);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not create the supplier. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setCreating(false);
        }
      }
    })();
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + suppliers.length < total;

  return (
    <section>
      <h2>Suppliers</h2>
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

      <form role="search" aria-label="Search and filter suppliers" onSubmit={handleSearchSubmit}>
        <div className="form-field">
          <label htmlFor="suppliers-search">Search</label>
          <input
            id="suppliers-search"
            type="search"
            value={searchInput}
            onChange={(event) => {
              setSearchInput(event.target.value);
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="suppliers-filter-status">Filter by approval status</label>
          <select
            id="suppliers-filter-status"
            value={approvalStatusFilter}
            onChange={(event) => {
              setApprovalStatusFilter(event.target.value as ApprovalStatus | '');
            }}
          >
            <option value="">All statuses</option>
            {(Object.keys(APPROVAL_STATUS_LABELS) as ApprovalStatus[]).map((status) => (
              <option key={status} value={status}>
                {APPROVAL_STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="suppliers-filter-risk">Filter by risk rating</label>
          <select
            id="suppliers-filter-risk"
            value={riskRatingFilter}
            onChange={(event) => {
              setRiskRatingFilter(event.target.value as RiskRating | '');
            }}
          >
            <option value="">All risk ratings</option>
            {(Object.keys(RISK_RATING_LABELS) as RiskRating[]).map((rating) => (
              <option key={rating} value={rating}>
                {RISK_RATING_LABELS[rating]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="suppliers-filter-preferred">
            <input
              id="suppliers-filter-preferred"
              type="checkbox"
              checked={preferredFilter}
              onChange={(event) => {
                setPreferredFilter(event.target.checked);
              }}
            />{' '}
            Preferred suppliers only
          </label>
        </div>
        <button type="submit" className="button">
          Search
        </button>
      </form>

      <form className="auth-form" onSubmit={handleCreate} aria-label="Create supplier">
        <h3>Create supplier</h3>
        {companies.length === 0 ? (
          <p>
            No companies exist yet. <Link to="/companies">Create a company first</Link>.
          </p>
        ) : (
          <div className="form-field">
            <label htmlFor="supplier-company">Company</label>
            <select
              id="supplier-company"
              required
              value={form.companyId}
              onChange={(event) => {
                setForm((current) => ({ ...current, companyId: event.target.value }));
              }}
            >
              <option value="">Choose a company</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="form-field">
          <label htmlFor="supplier-status">Approval status</label>
          <select
            id="supplier-status"
            value={form.approvalStatus}
            onChange={(event) => {
              setForm((current) => ({
                ...current,
                approvalStatus: event.target.value as ApprovalStatus,
              }));
            }}
          >
            {(Object.keys(APPROVAL_STATUS_LABELS) as ApprovalStatus[]).map((status) => (
              <option key={status} value={status}>
                {APPROVAL_STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="supplier-risk">Risk rating</label>
          <select
            id="supplier-risk"
            value={form.riskRating}
            onChange={(event) => {
              setForm((current) => ({
                ...current,
                riskRating: event.target.value as RiskRating | '',
              }));
            }}
          >
            <option value="">Not set</option>
            {(Object.keys(RISK_RATING_LABELS) as RiskRating[]).map((rating) => (
              <option key={rating} value={rating}>
                {RISK_RATING_LABELS[rating]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="supplier-preferred">
            <input
              id="supplier-preferred"
              type="checkbox"
              checked={form.isPreferred}
              onChange={(event) => {
                setForm((current) => ({ ...current, isPreferred: event.target.checked }));
              }}
            />{' '}
            Preferred supplier
          </label>
        </div>
        <div className="form-field">
          <label htmlFor="supplier-notes">Notes</label>
          <textarea
            id="supplier-notes"
            value={form.notes}
            onChange={(event) => {
              setForm((current) => ({ ...current, notes: event.target.value }));
            }}
          />
        </div>
        <button
          type="submit"
          className="button button--primary"
          disabled={creating || companies.length === 0}
        >
          {creating ? 'Creating…' : 'Create supplier'}
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

      {!loading && !loadError && suppliers.length === 0 && <p>No suppliers yet.</p>}

      {!loading && !loadError && suppliers.length > 0 && (
        <>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Company</th>
                  <th scope="col">Approval status</th>
                  <th scope="col">Risk rating</th>
                  <th scope="col">Preferred</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((supplier) => (
                  <tr key={supplier.id}>
                    <td>
                      <Link to={`/suppliers/${supplier.id}`}>
                        {companyNameById.get(supplier.company_id) ?? supplier.company_id}
                      </Link>
                    </td>
                    <td>{APPROVAL_STATUS_LABELS[supplier.approval_status]}</td>
                    <td>
                      {supplier.risk_rating ? RISK_RATING_LABELS[supplier.risk_rating] : 'Not set'}
                    </td>
                    <td>{supplier.is_preferred ? 'Yes' : 'No'}</td>
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
