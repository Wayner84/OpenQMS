import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { listDocuments } from '../documents/api';
import type { DocumentRecord } from '../documents/types';
import { listCompanies, listPeople } from '../people/api';
import type { Company, Person } from '../people/types';
import { listSuppliers } from '../suppliers/api';
import type { Supplier } from '../suppliers/types';
import { createCalibrationEvent, listCalibrationEvents } from './api';
import type { CalibrationEventListResponse, CalibrationResult } from './types';

const PAGE_SIZE = 20;
type PerformerType = 'none' | 'person' | 'supplier';

/** Immutable calibration history and new event form for one asset. */
export function CalibrationEventsPanel({
  assetId,
  onRecorded,
}: {
  assetId: string;
  onRecorded?: () => void;
}): ReactElement {
  const [history, setHistory] = useState<CalibrationEventListResponse | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [people, setPeople] = useState<Person[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState(false);
  const [optionsRefresh, setOptionsRefresh] = useState(0);
  const [performedAt, setPerformedAt] = useState('');
  const [performerType, setPerformerType] = useState<PerformerType>('none');
  const [performerId, setPerformerId] = useState('');
  const [certificateId, setCertificateId] = useState('');
  const [result, setResult] = useState<CalibrationResult>('pass');
  const [notes, setNotes] = useState('');
  const mountedRef = useRef(true);
  const historyRef = useRef(0);
  const optionsRef = useRef(0);
  const activeAssetRef = useRef(assetId);
  const key = `${assetId}:${offset}:${refresh}`;
  const activeKeyRef = useRef(key);

  useLayoutEffect(() => {
    activeAssetRef.current = assetId;
    activeKeyRef.current = key;
  }, [assetId, key]);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  useEffect(() => {
    setOffset(0);
    setPerformedAt('');
    setPerformerType('none');
    setPerformerId('');
    setCertificateId('');
    setResult('pass');
    setNotes('');
    setActionError(null);
    setSaving(false);
  }, [assetId]);

  useEffect(() => {
    const request = ++historyRef.current;
    setHistory(null);
    setLoadedKey(null);
    setError(null);
    setLoading(true);
    void listCalibrationEvents(assetId, { limit: PAGE_SIZE, offset })
      .then((response) => {
        if (!mountedRef.current || historyRef.current !== request || activeKeyRef.current !== key)
          return;
        setHistory(response);
        setLoadedKey(key);
      })
      .catch((reason: unknown) => {
        if (mountedRef.current && historyRef.current === request && activeKeyRef.current === key)
          setError(getErrorDetail(reason) ?? 'Could not load calibration events.');
      })
      .finally(() => {
        if (mountedRef.current && historyRef.current === request && activeKeyRef.current === key)
          setLoading(false);
      });
  }, [assetId, offset, refresh, key]);

  useEffect(() => {
    const request = ++optionsRef.current;
    setOptionsLoading(true);
    setOptionsError(false);
    void Promise.all([
      fetchAllPages<Person>((params) => listPeople(params)),
      fetchAllPages<Company>((params) => listCompanies(params)),
      fetchAllPages<Supplier>((params) => listSuppliers(params)),
      fetchAllPages<DocumentRecord>((params) => listDocuments(params)),
    ])
      .then(([peopleRows, companyRows, supplierRows, documentRows]) => {
        if (
          !mountedRef.current ||
          optionsRef.current !== request ||
          activeAssetRef.current !== assetId
        )
          return;
        setPeople(peopleRows);
        setCompanies(companyRows);
        setSuppliers(supplierRows);
        setDocuments(documentRows);
        setOptionsLoading(false);
      })
      .catch(() => {
        if (
          mountedRef.current &&
          optionsRef.current === request &&
          activeAssetRef.current === assetId
        ) {
          setOptionsError(true);
          setOptionsLoading(false);
        }
      });
  }, [assetId, optionsRefresh]);

  const submit = (formEvent: FormEvent<HTMLFormElement>): void => {
    formEvent.preventDefault();
    if (loadedKey !== key || !history || optionsLoading || optionsError || saving) return;
    if (!performedAt) {
      setActionError('Performed date is required.');
      return;
    }
    if (performerType !== 'none' && !performerId) {
      setActionError('Select a performer.');
      return;
    }
    const request = historyRef.current;
    const submittedAssetId = assetId;
    setSaving(true);
    setActionError(null);
    void createCalibrationEvent(assetId, {
      performed_at: performedAt,
      performed_by_id: performerType === 'person' ? performerId : null,
      performed_by_supplier_id: performerType === 'supplier' ? performerId : null,
      certificate_document_id: certificateId || null,
      result,
      notes: notes || null,
    })
      .then(() => {
        if (
          !mountedRef.current ||
          historyRef.current !== request ||
          activeAssetRef.current !== submittedAssetId
        )
          return;
        setPerformedAt('');
        setPerformerId('');
        setCertificateId('');
        setNotes('');
        setOffset(0);
        setRefresh((n) => n + 1);
        onRecorded?.();
      })
      .catch((reason: unknown) => {
        if (
          mountedRef.current &&
          historyRef.current === request &&
          activeAssetRef.current === submittedAssetId
        )
          setActionError(getErrorDetail(reason) ?? 'Could not record calibration event.');
      })
      .finally(() => {
        if (
          mountedRef.current &&
          historyRef.current === request &&
          activeAssetRef.current === submittedAssetId
        )
          setSaving(false);
      });
  };
  const current = loadedKey === key && !loading ? history : null;
  const companyNames = new Map(companies.map((company) => [company.id, company.name]));
  const personNames = new Map(
    people.map((person) => [person.id, `${person.first_name} ${person.last_name}`]),
  );
  const supplierNames = new Map(
    suppliers.map((supplier) => [
      supplier.id,
      companyNames.get(supplier.company_id) ?? supplier.company_id,
    ]),
  );
  const documentNames = new Map(
    documents.map((document) => [document.id, `${document.number} — ${document.title}`]),
  );

  return (
    <section aria-label="Calibration history">
      <h3>Calibration history</h3>
      {loading && <p role="status">Loading calibration events…</p>}
      {error && <p role="alert">{error}</p>}
      {error && (
        <button
          type="button"
          className="button"
          onClick={() => {
            setRefresh((n) => n + 1);
          }}
        >
          Retry events
        </button>
      )}
      {optionsError && (
        <>
          <p role="alert">Could not load performer and certificate options.</p>
          <button
            type="button"
            className="button"
            onClick={() => {
              setOptionsRefresh((n) => n + 1);
            }}
          >
            Retry options
          </button>
        </>
      )}
      {current && (
        <>
          <p>
            {current.total} calibration event{current.total === 1 ? '' : 's'}
          </p>
          {current.items.length === 0 ? (
            <p>No calibration events yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Performed</th>
                  <th>Result</th>
                  <th>Performer</th>
                  <th>Certificate</th>
                  <th>Next due snapshot</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {current.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <time dateTime={item.performed_at}>{item.performed_at}</time>
                    </td>
                    <td>{item.result}</td>
                    <td>
                      {item.performed_by_id
                        ? (personNames.get(item.performed_by_id) ?? item.performed_by_id)
                        : item.performed_by_supplier_id
                          ? (supplierNames.get(item.performed_by_supplier_id) ??
                            item.performed_by_supplier_id)
                          : 'Not recorded'}
                    </td>
                    <td>
                      {item.certificate_document_id ? (
                        <Link to={`/documents/${item.certificate_document_id}`}>
                          {documentNames.get(item.certificate_document_id) ?? 'View certificate'}
                        </Link>
                      ) : (
                        'None'
                      )}
                    </td>
                    <td>{item.next_due_date ?? 'Not set'}</td>
                    <td>{item.notes ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div>
            <button
              type="button"
              className="button"
              disabled={saving || offset === 0}
              onClick={() => {
                setOffset((n) => Math.max(0, n - PAGE_SIZE));
              }}
            >
              Previous events
            </button>
            <button
              type="button"
              className="button"
              disabled={saving || offset + PAGE_SIZE >= current.total}
              onClick={() => {
                setOffset((n) => n + PAGE_SIZE);
              }}
            >
              Next events
            </button>
          </div>
          {actionError && <p role="alert">{actionError}</p>}
          <form onSubmit={submit} aria-label="Record calibration event">
            <div className="form-field">
              <label htmlFor="event-performed">Performed at</label>
              <input
                id="event-performed"
                type="date"
                required
                value={performedAt}
                onChange={(event) => {
                  setPerformedAt(event.target.value);
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="event-result">Result</label>
              <select
                id="event-result"
                value={result}
                onChange={(event) => {
                  setResult(event.target.value as CalibrationResult);
                }}
              >
                <option value="pass">Pass</option>
                <option value="fail">Fail</option>
                <option value="limited">Limited</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="event-performer-type">Performer type</label>
              <select
                id="event-performer-type"
                value={performerType}
                onChange={(event) => {
                  setPerformerType(event.target.value as PerformerType);
                  setPerformerId('');
                }}
              >
                <option value="none">Not recorded</option>
                <option value="person">Person</option>
                <option value="supplier">Supplier</option>
              </select>
            </div>
            {performerType === 'person' && (
              <div className="form-field">
                <label htmlFor="event-person">Person</label>
                <select
                  id="event-person"
                  value={performerId}
                  required
                  onChange={(event) => {
                    setPerformerId(event.target.value);
                  }}
                >
                  <option value="">Choose a person</option>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.first_name} {person.last_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {performerType === 'supplier' && (
              <div className="form-field">
                <label htmlFor="event-supplier">Supplier</label>
                <select
                  id="event-supplier"
                  value={performerId}
                  required
                  onChange={(event) => {
                    setPerformerId(event.target.value);
                  }}
                >
                  <option value="">Choose a supplier</option>
                  {suppliers.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>
                      {supplierNames.get(supplier.id)}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="form-field">
              <label htmlFor="event-certificate">Certificate document</label>
              <select
                id="event-certificate"
                value={certificateId}
                onChange={(event) => {
                  setCertificateId(event.target.value);
                }}
              >
                <option value="">No certificate</option>
                {documents.map((document) => (
                  <option key={document.id} value={document.id}>
                    {documentNames.get(document.id)}
                  </option>
                ))}
              </select>
            </div>
            <p>
              Upload a certificate in Documents first, then select it here. Event records cannot be
              edited.
            </p>
            <button
              type="button"
              className="button"
              disabled={optionsLoading || saving}
              onClick={() => {
                setOptionsRefresh((value) => value + 1);
              }}
            >
              Refresh options
            </button>
            <div className="form-field">
              <label htmlFor="event-notes">Notes</label>
              <textarea
                id="event-notes"
                value={notes}
                onChange={(event) => {
                  setNotes(event.target.value);
                }}
              />
            </div>
            <button
              type="submit"
              className="button button--primary"
              disabled={saving || optionsLoading || optionsError}
            >
              {saving ? 'Recording…' : 'Record calibration'}
            </button>
          </form>
        </>
      )}
    </section>
  );
}
