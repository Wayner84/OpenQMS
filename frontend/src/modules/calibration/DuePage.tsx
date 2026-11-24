import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { Link } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { listDue } from './api';
import type { DueListResponse } from './types';

const PAGE_SIZE = 20;
const MAX_WINDOW = 3650;

/** Organisation-scoped calibration and maintenance obligations. */
export function DuePage(): ReactElement {
  const [windowInput, setWindowInput] = useState('');
  const [withinDays, setWithinDays] = useState<number | undefined>();
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState<DueListResponse | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const requestRef = useRef(0);
  const key = `${withinDays ?? 'default'}:${offset}:${refresh}`;
  const activeKeyRef = useRef(key);

  useLayoutEffect(() => {
    activeKeyRef.current = key;
  }, [key]);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  useEffect(() => {
    const request = ++requestRef.current;
    setResult(null);
    setLoadedKey(null);
    setError(null);
    setLoading(true);
    void listDue({ ...(withinDays !== undefined ? { withinDays } : {}), limit: PAGE_SIZE, offset })
      .then((response) => {
        if (!mountedRef.current || requestRef.current !== request || activeKeyRef.current !== key)
          return;
        setResult(response);
        setLoadedKey(key);
      })
      .catch((reason: unknown) => {
        if (mountedRef.current && requestRef.current === request && activeKeyRef.current === key)
          setError(getErrorDetail(reason) ?? 'Could not load due items.');
      })
      .finally(() => {
        if (mountedRef.current && requestRef.current === request && activeKeyRef.current === key)
          setLoading(false);
      });
  }, [withinDays, offset, refresh, key]);

  const apply = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const value = windowInput === '' ? undefined : Number(windowInput);
    if (value !== undefined && (!Number.isInteger(value) || value < 0 || value > MAX_WINDOW)) {
      setError(`Window must be between 0 and ${MAX_WINDOW} days.`);
      return;
    }
    setWithinDays(value);
    setOffset(0);
    setRefresh((n) => n + 1);
  };
  const current = loadedKey === key && !loading ? result : null;
  return (
    <section>
      <h2>Calibration and maintenance due</h2>
      <p>
        <Link to="/calibration/assets">Asset register</Link>
      </p>
      <form onSubmit={apply} aria-label="Due window">
        <label htmlFor="due-window">Within days (blank uses organisation default)</label>
        <input
          id="due-window"
          type="number"
          min="0"
          max={MAX_WINDOW}
          step="1"
          value={windowInput}
          onChange={(event) => {
            setWindowInput(event.target.value);
          }}
        />
        <button type="submit" className="button">
          Apply window
        </button>
      </form>
      {loading && <p role="status">Loading due items…</p>}
      {error && <p role="alert">{error}</p>}
      {error && !loading && (
        <button
          type="button"
          className="button"
          onClick={() => {
            setRefresh((n) => n + 1);
          }}
        >
          Retry
        </button>
      )}
      {current && (
        <>
          <p>
            Showing {current.total ? offset + 1 : 0}–
            {Math.min(offset + current.items.length, current.total)} of {current.total} (within{' '}
            {current.within_days} {current.within_days === 1 ? 'day' : 'days'})
          </p>
          {current.items.length === 0 ? (
            <p>No due items in this window.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Type</th>
                  <th>Next due</th>
                </tr>
              </thead>
              <tbody>
                {current.items.map((item) => (
                  <tr key={`${item.asset_id}:${item.due_type}`}>
                    <td>
                      <Link to={`/calibration/assets/${item.asset_id}`}>
                        {item.asset_tag} — {item.asset_name}
                      </Link>
                    </td>
                    <td>{item.due_type === 'calibration' ? 'Calibration' : 'Maintenance'}</td>
                    <td>
                      <time dateTime={item.next_due_date}>{item.next_due_date}</time>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div>
            <button
              type="button"
              className="button"
              disabled={offset === 0}
              onClick={() => {
                setOffset((n) => Math.max(0, n - PAGE_SIZE));
              }}
            >
              Previous
            </button>
            <button
              type="button"
              className="button"
              disabled={offset + PAGE_SIZE >= current.total}
              onClick={() => {
                setOffset((n) => n + PAGE_SIZE);
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
