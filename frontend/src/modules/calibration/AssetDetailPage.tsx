import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { listPeople } from '../people/api';
import type { Person } from '../people/types';
import { deleteAsset, getAsset, updateAsset } from './api';
import { CalibrationSchedulePanel } from './CalibrationSchedulePanel';
import type { Asset, AssetStatus, AssetType, AssetWriteRequest } from './types';

/** Metadata controls for an organisation-scoped asset. */
export function AssetDetailPage(): ReactElement {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [asset, setAsset] = useState<Asset | null>(null);
  const [form, setForm] = useState<AssetWriteRequest | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [optionsRefresh, setOptionsRefresh] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const mountedRef = useRef(true);
  const requestRef = useRef(0);
  const peopleRequestRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const request = ++peopleRequestRef.current;
    setOptionsLoading(true);
    setOptionsError(null);
    void fetchAllPages<Person>((params) => listPeople(params))
      .then((items) => {
        if (mountedRef.current && peopleRequestRef.current === request) {
          setPeople(items);
          setOptionsLoading(false);
        }
      })
      .catch(() => {
        if (mountedRef.current && peopleRequestRef.current === request) {
          setOptionsError('Could not load asset owners. Please try again.');
          setOptionsLoading(false);
        }
      });
  }, [optionsRefresh]);

  useEffect(() => {
    const request = ++requestRef.current;
    setAsset(null);
    setForm(null);
    setError(null);
    setActionError(null);
    setSaving(false);
    setDeleting(false);
    setLoading(true);
    if (!id) {
      setError('Asset not found.');
      setLoading(false);
      return;
    }
    void getAsset(id)
      .then((result) => {
        if (mountedRef.current && requestRef.current === request) {
          setAsset(result);
          setForm({
            asset_tag: result.asset_tag,
            name: result.name,
            asset_type: result.asset_type,
            serial_number: result.serial_number,
            location: result.location,
            owner_id: result.owner_id,
            status: result.status,
            purchase_date: result.purchase_date,
          });
        }
      })
      .catch((reason: unknown) => {
        if (mountedRef.current && requestRef.current === request)
          setError(getErrorDetail(reason) ?? 'Could not load asset.');
      })
      .finally(() => {
        if (mountedRef.current && requestRef.current === request) setLoading(false);
      });
  }, [id]);

  const save = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id || !form || optionsLoading || optionsError) return;
    const request = requestRef.current;
    setSaving(true);
    setActionError(null);
    void updateAsset(id, form)
      .then((result) => {
        if (mountedRef.current && requestRef.current === request) setAsset(result);
      })
      .catch((reason: unknown) => {
        if (mountedRef.current && requestRef.current === request)
          setActionError(getErrorDetail(reason) ?? 'Could not update the asset.');
      })
      .finally(() => {
        if (mountedRef.current && requestRef.current === request) setSaving(false);
      });
  };

  const remove = (): void => {
    if (!id || !asset || !window.confirm(`Delete asset ${asset.asset_tag}?`)) return;
    const request = requestRef.current;
    setDeleting(true);
    setActionError(null);
    void deleteAsset(id)
      .then(() => {
        if (mountedRef.current && requestRef.current === request)
          void navigate('/calibration/assets');
      })
      .catch((reason: unknown) => {
        if (mountedRef.current && requestRef.current === request)
          setActionError(getErrorDetail(reason) ?? 'Could not delete the asset.');
      })
      .finally(() => {
        if (mountedRef.current && requestRef.current === request) setDeleting(false);
      });
  };

  return (
    <section>
      <h2>Asset details</h2>
      <p>
        <Link to="/calibration/assets">Back to assets</Link>
      </p>
      {loading && <p role="status">Loading…</p>}
      {error && <p role="alert">{error}</p>}
      {optionsError && (
        <div>
          <p role="alert">{optionsError}</p>
          <button
            type="button"
            className="button"
            onClick={() => {
              setOptionsRefresh((value) => value + 1);
            }}
          >
            Retry owners
          </button>
        </div>
      )}
      {actionError && <p role="alert">{actionError}</p>}
      {asset && form && (
        <>
          <h3>{asset.name}</h3>
          <p>{asset.asset_tag}</p>
          <form className="auth-form" aria-label="Edit asset" onSubmit={save}>
            <div className="form-field">
              <label htmlFor="edit-asset-tag">Asset tag</label>
              <input
                id="edit-asset-tag"
                required
                value={form.asset_tag}
                onChange={(event) => {
                  setForm({ ...form, asset_tag: event.target.value });
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="edit-asset-name">Name</label>
              <input
                id="edit-asset-name"
                required
                value={form.name}
                onChange={(event) => {
                  setForm({ ...form, name: event.target.value });
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="edit-asset-type">Type</label>
              <select
                id="edit-asset-type"
                value={form.asset_type}
                onChange={(event) => {
                  setForm({ ...form, asset_type: event.target.value as AssetType });
                }}
              >
                <option value="measuring_equipment">Measuring equipment</option>
                <option value="inspection_equipment">Inspection equipment</option>
                <option value="company_asset">Company asset</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="edit-asset-serial">Serial number</label>
              <input
                id="edit-asset-serial"
                value={form.serial_number ?? ''}
                onChange={(event) => {
                  setForm({ ...form, serial_number: event.target.value || null });
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="edit-asset-location">Location</label>
              <input
                id="edit-asset-location"
                value={form.location ?? ''}
                onChange={(event) => {
                  setForm({ ...form, location: event.target.value || null });
                }}
              />
            </div>
            <div className="form-field">
              <label htmlFor="edit-asset-owner">Owner</label>
              <select
                id="edit-asset-owner"
                value={form.owner_id ?? ''}
                disabled={optionsLoading || !!optionsError}
                onChange={(event) => {
                  setForm({ ...form, owner_id: event.target.value || null });
                }}
              >
                <option value="">No owner</option>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.first_name} {person.last_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="edit-asset-status">Status</label>
              <select
                id="edit-asset-status"
                value={form.status}
                onChange={(event) => {
                  setForm({ ...form, status: event.target.value as AssetStatus });
                }}
              >
                <option value="in_service">In service</option>
                <option value="out_of_service">Out of service</option>
                <option value="retired">Retired</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="edit-asset-purchased">Purchase date</label>
              <input
                id="edit-asset-purchased"
                type="date"
                value={form.purchase_date ?? ''}
                onChange={(event) => {
                  setForm({ ...form, purchase_date: event.target.value || null });
                }}
              />
            </div>
            <button
              type="submit"
              className="button button--primary"
              disabled={saving || deleting || optionsLoading || !!optionsError}
            >
              {saving ? 'Saving…' : 'Save asset'}
            </button>
          </form>
          <button type="button" className="button" disabled={saving || deleting} onClick={remove}>
            {deleting ? 'Deleting…' : 'Delete asset'}
          </button>
          <CalibrationSchedulePanel assetId={asset.id} />
        </>
      )}
    </section>
  );
}
