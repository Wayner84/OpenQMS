import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { listPeople } from '../people/api';
import type { Person } from '../people/types';
import { createAsset, listAssets } from './api';
import type { Asset, AssetStatus, AssetType } from './types';

const PAGE_SIZE = 20;
const TYPE_LABELS: Record<AssetType, string> = {
  measuring_equipment: 'Measuring equipment',
  inspection_equipment: 'Inspection equipment',
  company_asset: 'Company asset',
};
const STATUS_LABELS: Record<AssetStatus, string> = {
  in_service: 'In service',
  out_of_service: 'Out of service',
  retired: 'Retired',
};

/** Search and register calibration assets; owners are selected from the scoped People directory. */
export function AssetsPage(): ReactElement {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsRefresh, setOptionsRefresh] = useState(0);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [assetType, setAssetType] = useState<AssetType | ''>('');
  const [status, setStatus] = useState<AssetStatus | ''>('');
  const [location, setLocation] = useState('');
  const [draftAssetType, setDraftAssetType] = useState<AssetType | ''>('');
  const [draftStatus, setDraftStatus] = useState<AssetStatus | ''>('');
  const [draftLocation, setDraftLocation] = useState('');
  const [form, setForm] = useState({
    assetTag: '',
    name: '',
    assetType: 'measuring_equipment' as AssetType,
    serialNumber: '',
    location: '',
    ownerId: '',
    status: 'in_service' as AssetStatus,
  });
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const mountedRef = useRef(true);
  const listRequestRef = useRef(0);
  const peopleRequestRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const requestId = ++peopleRequestRef.current;
    setOptionsLoading(true);
    setOptionsError(null);
    void fetchAllPages<Person>((params) => listPeople(params))
      .then((items) => {
        if (mountedRef.current && peopleRequestRef.current === requestId) {
          setPeople(items);
          setOptionsLoading(false);
        }
      })
      .catch(() => {
        if (mountedRef.current && peopleRequestRef.current === requestId) {
          setOptionsError('Could not load asset owners. Please try again.');
          setOptionsLoading(false);
        }
      });
  }, [optionsRefresh]);

  const loadAssets = useCallback(
    async (nextOffset: number) => {
      const requestId = ++listRequestRef.current;
      setLoading(true);
      setLoadError(null);
      try {
        const result = await listAssets({
          search: search || undefined,
          assetType: assetType || undefined,
          status: status || undefined,
          location: location || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        if (mountedRef.current && listRequestRef.current === requestId) {
          setAssets(result.items);
          setTotal(result.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current && listRequestRef.current === requestId)
          setLoadError('Could not load assets. Please try again.');
      } finally {
        if (mountedRef.current && listRequestRef.current === requestId) setLoading(false);
      }
    },
    [search, assetType, status, location],
  );

  useEffect(() => {
    void loadAssets(0);
  }, [loadAssets, refresh]);

  const submitSearch = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setSearch(searchInput);
    setAssetType(draftAssetType);
    setStatus(draftStatus);
    setLocation(draftLocation);
  };
  const submitCreate = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setActionError(null);
    setCreating(true);
    void (async () => {
      try {
        await createAsset({
          asset_tag: form.assetTag,
          name: form.name,
          asset_type: form.assetType,
          serial_number: form.serialNumber || undefined,
          location: form.location || undefined,
          owner_id: form.ownerId || undefined,
          status: form.status,
        });
        if (mountedRef.current)
          setForm({
            assetTag: '',
            name: '',
            assetType: 'measuring_equipment',
            serialNumber: '',
            location: '',
            ownerId: '',
            status: 'in_service',
          });
        if (mountedRef.current) setRefresh((current) => current + 1);
      } catch (error) {
        if (mountedRef.current)
          setActionError(getErrorDetail(error) ?? 'Could not create the asset. Please try again.');
      } finally {
        if (mountedRef.current) setCreating(false);
      }
    })();
  };

  return (
    <section>
      <h2>Calibration assets</h2>
      {actionError && (
        <p role="alert" className="auth-form__error">
          {actionError}
        </p>
      )}
      {optionsError && (
        <div>
          <p role="alert" className="auth-form__error">
            {optionsError}
          </p>
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
      <form role="search" aria-label="Search and filter assets" onSubmit={submitSearch}>
        <div className="form-field">
          <label htmlFor="asset-search">Search</label>
          <input
            id="asset-search"
            type="search"
            value={searchInput}
            onChange={(event) => {
              setSearchInput(event.target.value);
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="asset-filter-type">Filter by type</label>
          <select
            id="asset-filter-type"
            value={draftAssetType}
            onChange={(event) => {
              setDraftAssetType(event.target.value as AssetType | '');
            }}
          >
            <option value="">All types</option>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="asset-filter-status">Filter by status</label>
          <select
            id="asset-filter-status"
            value={draftStatus}
            onChange={(event) => {
              setDraftStatus(event.target.value as AssetStatus | '');
            }}
          >
            <option value="">All statuses</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="asset-filter-location">Filter by location</label>
          <input
            id="asset-filter-location"
            value={draftLocation}
            onChange={(event) => {
              setDraftLocation(event.target.value);
            }}
          />
        </div>
        <button type="submit" className="button">
          Search
        </button>
      </form>
      <form className="auth-form" onSubmit={submitCreate} aria-label="Create asset">
        <h3>Create asset</h3>
        <div className="form-field">
          <label htmlFor="asset-tag">Asset tag</label>
          <input
            id="asset-tag"
            required
            value={form.assetTag}
            onChange={(event) => {
              setForm((current) => ({ ...current, assetTag: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="asset-name">Name</label>
          <input
            id="asset-name"
            required
            value={form.name}
            onChange={(event) => {
              setForm((current) => ({ ...current, name: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="asset-type">Type</label>
          <select
            id="asset-type"
            value={form.assetType}
            onChange={(event) => {
              setForm((current) => ({ ...current, assetType: event.target.value as AssetType }));
            }}
          >
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="asset-serial-number">Serial number</label>
          <input
            id="asset-serial-number"
            value={form.serialNumber}
            onChange={(event) => {
              setForm((current) => ({ ...current, serialNumber: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="asset-location">Location</label>
          <input
            id="asset-location"
            value={form.location}
            onChange={(event) => {
              setForm((current) => ({ ...current, location: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="asset-owner">Owner</label>
          <select
            id="asset-owner"
            value={form.ownerId}
            disabled={optionsLoading || optionsError !== null}
            onChange={(event) => {
              setForm((current) => ({ ...current, ownerId: event.target.value }));
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
          <label htmlFor="asset-status">Status</label>
          <select
            id="asset-status"
            value={form.status}
            onChange={(event) => {
              setForm((current) => ({ ...current, status: event.target.value as AssetStatus }));
            }}
          >
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="button button--primary"
          disabled={creating || optionsLoading || optionsError !== null}
        >
          {creating ? 'Creating…' : 'Create asset'}
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
      {!loading && !loadError && assets.length === 0 && <p>No assets found.</p>}
      {!loading && !loadError && assets.length > 0 && (
        <>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Asset tag</th>
                  <th scope="col">Name</th>
                  <th scope="col">Type</th>
                  <th scope="col">Location</th>
                  <th scope="col">Owner</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {assets.map((asset) => {
                  const owner = people.find((person) => person.id === asset.owner_id);
                  return (
                    <tr key={asset.id}>
                      <td>{asset.asset_tag}</td>
                      <td>{asset.name}</td>
                      <td>{TYPE_LABELS[asset.asset_type]}</td>
                      <td>{asset.location ?? ''}</td>
                      <td>{owner ? `${owner.first_name} ${owner.last_name}` : ''}</td>
                      <td>{STATUS_LABELS[asset.status]}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p>{total} assets</p>
          <div className="pagination">
            <button
              type="button"
              className="button"
              disabled={offset === 0}
              onClick={() => void loadAssets(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <button
              type="button"
              className="button"
              disabled={offset + assets.length >= total}
              onClick={() => void loadAssets(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
