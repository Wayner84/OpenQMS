import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { useParams } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { listCompanies } from '../people/api';
import type { Company } from '../people/types';
import {
  createCertification,
  createPerformanceRecord,
  deleteCertification,
  getSupplier,
  listCertifications,
  listPerformanceRecords,
  updateCertification,
  updateSupplier,
} from './api';
import type {
  ApprovalStatus,
  RiskRating,
  Supplier,
  SupplierCertification,
  SupplierPerformanceRecord,
} from './types';

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

/** A certification within this many days of `expiry_date` (or already expired) is
 * highlighted, matching the organisation's default reminder window
 * (docs/Database.md#certification-expiry-reminder-window) as a practical default
 * for this purely visual cue — the actual expiring-list endpoint is the source of
 * truth for the configured value. */
const EXPIRY_WARNING_WINDOW_DAYS = 30;

function isExpiringSoon(expiryDate: string | null): boolean {
  if (!expiryDate) {
    return false;
  }
  const msPerDay = 24 * 60 * 60 * 1000;
  const daysUntilExpiry = (new Date(expiryDate).getTime() - Date.now()) / msPerDay;
  return daysUntilExpiry <= EXPIRY_WARNING_WINDOW_DAYS;
}

interface MetadataForm {
  companyId: string;
  approvalStatus: ApprovalStatus;
  riskRating: RiskRating | '';
  isPreferred: boolean;
  notes: string;
}

function toMetadataForm(supplier: Supplier): MetadataForm {
  return {
    companyId: supplier.company_id,
    approvalStatus: supplier.approval_status,
    riskRating: supplier.risk_rating ?? '',
    isPreferred: supplier.is_preferred,
    notes: supplier.notes ?? '',
  };
}

interface CertificationForm {
  certificationType: string;
  issuedDate: string;
  expiryDate: string;
}

const emptyCertificationForm: CertificationForm = {
  certificationType: '',
  issuedDate: '',
  expiryDate: '',
};

function toCertificationForm(certification: SupplierCertification): CertificationForm {
  return {
    certificationType: certification.certification_type,
    issuedDate: certification.issued_date ?? '',
    expiryDate: certification.expiry_date ?? '',
  };
}

interface PerformanceForm {
  period: string;
  score: string;
  notes: string;
}

const emptyPerformanceForm: PerformanceForm = { period: '', score: '', notes: '' };

/**
 * A single supplier: metadata (with an edit form), certifications (add/edit/delete,
 * with an expiry-highlighted state), and performance records (append-only list with
 * an add form), per docs/modules/Suppliers.md.
 */
export function SupplierDetailPage(): ReactElement {
  const { id } = useParams<{ id: string }>();

  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [certifications, setCertifications] = useState<SupplierCertification[]>([]);
  const [performanceRecords, setPerformanceRecords] = useState<SupplierPerformanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [editingMetadata, setEditingMetadata] = useState(false);
  const [metadataForm, setMetadataForm] = useState<MetadataForm>({
    companyId: '',
    approvalStatus: 'pending',
    riskRating: '',
    isPreferred: false,
    notes: '',
  });
  const [savingMetadata, setSavingMetadata] = useState(false);

  const [certificationForm, setCertificationForm] =
    useState<CertificationForm>(emptyCertificationForm);
  const [editingCertificationId, setEditingCertificationId] = useState<string | null>(null);
  const [savingCertification, setSavingCertification] = useState(false);
  const [pendingCertificationIds, setPendingCertificationIds] = useState<ReadonlySet<string>>(
    new Set(),
  );

  const [performanceForm, setPerformanceForm] = useState<PerformanceForm>(emptyPerformanceForm);
  const [savingPerformance, setSavingPerformance] = useState(false);

  const mountedRef = useRef(true);
  const currentSupplierIdRef = useRef(id);
  const loadRequestIdRef = useRef(0);
  currentSupplierIdRef.current = id;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void fetchAllPages<Company>((params) => listCompanies(params)).then((items) => {
      if (mountedRef.current) {
        setCompanies(items);
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

  const loadAll = useCallback(async () => {
    if (!id || currentSupplierIdRef.current !== id) {
      return;
    }
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    setLoadError(null);
    try {
      const [supplierResult, certificationItems, performanceItems] = await Promise.all([
        getSupplier(id),
        fetchAllPages<SupplierCertification>((params) => listCertifications(id, params)),
        fetchAllPages<SupplierPerformanceRecord>((params) => listPerformanceRecords(id, params)),
      ]);
      if (
        mountedRef.current &&
        currentSupplierIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setSupplier(supplierResult);
        setCertifications(certificationItems);
        setPerformanceRecords(performanceItems);
      }
    } catch {
      if (
        mountedRef.current &&
        currentSupplierIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoadError('Could not load this supplier. Please try again.');
      }
    } finally {
      if (
        mountedRef.current &&
        currentSupplierIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoading(false);
      }
    }
  }, [id]);

  useEffect(() => {
    setSupplier(null);
    setCertifications([]);
    setPerformanceRecords([]);
    setLoadError(null);
    setActionError(null);
    setEditingMetadata(false);
    setCertificationForm(emptyCertificationForm);
    setEditingCertificationId(null);
    setPerformanceForm(emptyPerformanceForm);
  }, [id]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const startEditMetadata = (): void => {
    if (!supplier) {
      return;
    }
    setActionError(null);
    setMetadataForm(toMetadataForm(supplier));
    setEditingMetadata(true);
  };

  const cancelEditMetadata = (): void => {
    setEditingMetadata(false);
  };

  const handleMetadataSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id) {
      return;
    }
    setActionError(null);
    setSavingMetadata(true);
    const actionSupplierId = id;
    void (async () => {
      try {
        await updateSupplier(id, {
          company_id: metadataForm.companyId,
          approval_status: metadataForm.approvalStatus,
          risk_rating: metadataForm.riskRating || undefined,
          is_preferred: metadataForm.isPreferred,
          notes: metadataForm.notes || undefined,
        });
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setEditingMetadata(false);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setActionError(getErrorDetail(err) ?? 'Could not save these changes. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setSavingMetadata(false);
        }
      }
    })();
  };

  const startEditCertification = (certification: SupplierCertification): void => {
    setActionError(null);
    setEditingCertificationId(certification.id);
    setCertificationForm(toCertificationForm(certification));
  };

  const cancelEditCertification = (): void => {
    setEditingCertificationId(null);
    setCertificationForm(emptyCertificationForm);
  };

  const handleCertificationSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id) {
      return;
    }
    setActionError(null);
    setSavingCertification(true);
    const actionSupplierId = id;
    const payload = {
      certification_type: certificationForm.certificationType,
      issued_date: certificationForm.issuedDate || undefined,
      expiry_date: certificationForm.expiryDate || undefined,
    };
    void (async () => {
      try {
        if (editingCertificationId) {
          await updateCertification(id, editingCertificationId, payload);
        } else {
          await createCertification(id, payload);
        }
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setCertificationForm(emptyCertificationForm);
          setEditingCertificationId(null);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setActionError(
            getErrorDetail(err) ??
              `Could not ${editingCertificationId ? 'update' : 'add'} the certification. Please try again.`,
          );
        }
      } finally {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setSavingCertification(false);
        }
      }
    })();
  };

  const handleDeleteCertification = (certification: SupplierCertification): void => {
    if (!id) {
      return;
    }
    setActionError(null);
    setPendingCertificationIds((current) => new Set(current).add(certification.id));
    const actionSupplierId = id;
    void (async () => {
      try {
        await deleteCertification(id, certification.id);
        if (currentSupplierIdRef.current === actionSupplierId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not delete the certification. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setPendingCertificationIds((current) => {
            const next = new Set(current);
            next.delete(certification.id);
            return next;
          });
        }
      }
    })();
  };

  const handlePerformanceSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id) {
      return;
    }
    setActionError(null);
    setSavingPerformance(true);
    const actionSupplierId = id;
    void (async () => {
      try {
        await createPerformanceRecord(id, {
          period: performanceForm.period,
          score: performanceForm.score,
          notes: performanceForm.notes || undefined,
        });
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setPerformanceForm(emptyPerformanceForm);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not add the performance record. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentSupplierIdRef.current === actionSupplierId) {
          setSavingPerformance(false);
        }
      }
    })();
  };

  if (!id) {
    return <p role="alert">No supplier specified.</p>;
  }

  return (
    <section>
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

      {!loading && !loadError && supplier && (
        <>
          <h2>{companyNameById.get(supplier.company_id) ?? supplier.company_id}</h2>
          <p>
            Approval status: {APPROVAL_STATUS_LABELS[supplier.approval_status]}
            {' · '}
            Risk rating:{' '}
            {supplier.risk_rating ? RISK_RATING_LABELS[supplier.risk_rating] : 'Not set'}
            {' · '}
            {supplier.is_preferred ? 'Preferred supplier' : 'Not a preferred supplier'}
          </p>
          {actionError && (
            <p role="alert" className="auth-form__error">
              {actionError}
            </p>
          )}
          <button
            type="button"
            className="button"
            onClick={editingMetadata ? cancelEditMetadata : startEditMetadata}
          >
            {editingMetadata ? 'Cancel editing' : 'Edit details'}
          </button>
          {editingMetadata && (
            <form
              className="auth-form"
              onSubmit={handleMetadataSubmit}
              aria-label="Edit supplier details"
            >
              <div className="form-field">
                <label htmlFor="metadata-company">Company</label>
                <select
                  id="metadata-company"
                  required
                  value={metadataForm.companyId}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, companyId: event.target.value }));
                  }}
                >
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="metadata-status">Approval status</label>
                <select
                  id="metadata-status"
                  value={metadataForm.approvalStatus}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
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
                <label htmlFor="metadata-risk">Risk rating</label>
                <select
                  id="metadata-risk"
                  value={metadataForm.riskRating}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
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
                <label htmlFor="metadata-preferred">
                  <input
                    id="metadata-preferred"
                    type="checkbox"
                    checked={metadataForm.isPreferred}
                    onChange={(event) => {
                      setMetadataForm((current) => ({
                        ...current,
                        isPreferred: event.target.checked,
                      }));
                    }}
                  />{' '}
                  Preferred supplier
                </label>
              </div>
              <div className="form-field">
                <label htmlFor="metadata-notes">Notes</label>
                <textarea
                  id="metadata-notes"
                  value={metadataForm.notes}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, notes: event.target.value }));
                  }}
                />
              </div>
              <button type="submit" className="button button--primary" disabled={savingMetadata}>
                {savingMetadata ? 'Saving…' : 'Save changes'}
              </button>{' '}
              <button type="button" className="button" onClick={cancelEditMetadata}>
                Cancel
              </button>
            </form>
          )}

          <h3>Certifications</h3>
          <form
            className="auth-form"
            onSubmit={handleCertificationSubmit}
            aria-label={editingCertificationId ? 'Edit certification' : 'Add certification'}
          >
            <div className="form-field">
              <label htmlFor="certification-type">Certification type</label>
              <input
                id="certification-type"
                required
                value={certificationForm.certificationType}
                onChange={(event) => {
                  setCertificationForm((current) => ({
                    ...current,
                    certificationType: event.target.value,
                  }));
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="certification-issued">Issued date</label>
              <input
                id="certification-issued"
                type="date"
                value={certificationForm.issuedDate}
                onChange={(event) => {
                  setCertificationForm((current) => ({
                    ...current,
                    issuedDate: event.target.value,
                  }));
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="certification-expiry">Expiry date</label>
              <input
                id="certification-expiry"
                type="date"
                value={certificationForm.expiryDate}
                onChange={(event) => {
                  setCertificationForm((current) => ({
                    ...current,
                    expiryDate: event.target.value,
                  }));
                }}
              />
            </div>
            <button type="submit" className="button button--primary" disabled={savingCertification}>
              {savingCertification
                ? 'Saving…'
                : editingCertificationId
                  ? 'Save changes'
                  : 'Add certification'}
            </button>{' '}
            {editingCertificationId && (
              <button type="button" className="button" onClick={cancelEditCertification}>
                Cancel
              </button>
            )}
          </form>

          {certifications.length === 0 ? (
            <p>No certifications recorded yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Type</th>
                    <th scope="col">Issued</th>
                    <th scope="col">Expiry</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {certifications.map((certification) => {
                    const isPending = pendingCertificationIds.has(certification.id);
                    const expiringSoon = isExpiringSoon(certification.expiry_date);
                    return (
                      <tr
                        key={certification.id}
                        className={expiringSoon ? 'supplier-certification--expiring' : undefined}
                      >
                        <td>{certification.certification_type}</td>
                        <td>{certification.issued_date ?? 'Not set'}</td>
                        <td>
                          {certification.expiry_date ?? 'Not set'}
                          {expiringSoon && <strong> (expiring soon)</strong>}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="button"
                            disabled={isPending}
                            onClick={() => {
                              startEditCertification(certification);
                            }}
                          >
                            Edit {certification.certification_type}
                          </button>{' '}
                          <button
                            type="button"
                            className="button"
                            disabled={isPending}
                            onClick={() => {
                              handleDeleteCertification(certification);
                            }}
                          >
                            Delete {certification.certification_type}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <h3>Performance records</h3>
          <form
            className="auth-form"
            onSubmit={handlePerformanceSubmit}
            aria-label="Add performance record"
          >
            <div className="form-field">
              <label htmlFor="performance-period">Period</label>
              <input
                id="performance-period"
                required
                placeholder="2026-Q3"
                value={performanceForm.period}
                onChange={(event) => {
                  setPerformanceForm((current) => ({ ...current, period: event.target.value }));
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="performance-score">Score</label>
              <input
                id="performance-score"
                required
                type="number"
                step="0.01"
                value={performanceForm.score}
                onChange={(event) => {
                  setPerformanceForm((current) => ({ ...current, score: event.target.value }));
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="performance-notes">Notes</label>
              <textarea
                id="performance-notes"
                value={performanceForm.notes}
                onChange={(event) => {
                  setPerformanceForm((current) => ({ ...current, notes: event.target.value }));
                }}
              />
            </div>
            <button type="submit" className="button button--primary" disabled={savingPerformance}>
              {savingPerformance ? 'Saving…' : 'Add performance record'}
            </button>
          </form>

          {performanceRecords.length === 0 ? (
            <p>No performance records yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Period</th>
                    <th scope="col">Score</th>
                    <th scope="col">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {performanceRecords.map((record) => (
                    <tr key={record.id}>
                      <td>{record.period}</td>
                      <td>{record.score}</td>
                      <td>{record.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
