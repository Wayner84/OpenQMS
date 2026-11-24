import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';

import { ApiError, getErrorDetail } from '../../shared/api/client';
import {
  createMaintenanceSchedule,
  getMaintenanceSchedule,
  updateMaintenanceSchedule,
} from './api';
import type { CalibrationIntervalUnit, MaintenanceSchedule } from './types';

/** Maintenance schedule for one asset; an empty GET is not a missing asset. */
export function MaintenanceSchedulePanel({ assetId }: { assetId: string }): ReactElement {
  const [schedule, setSchedule] = useState<MaintenanceSchedule | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [intervalValue, setIntervalValue] = useState('6');
  const [intervalUnit, setIntervalUnit] = useState<CalibrationIntervalUnit>('months');
  const [nextDueDate, setNextDueDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createConflict, setCreateConflict] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const mountedRef = useRef(true);
  const requestRef = useRef(0);
  const activeAssetRef = useRef(assetId);

  // Mutations may settle after an asset switch commits but before its read effect runs.
  useLayoutEffect(() => {
    activeAssetRef.current = assetId;
  }, [assetId]);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const request = ++requestRef.current;
    setSchedule(null);
    setLoadedFor(null);
    setError(null);
    setCreateConflict(false);
    setLoading(true);
    setSaving(false);
    void getMaintenanceSchedule(assetId)
      .then((result) => {
        if (
          !mountedRef.current ||
          requestRef.current !== request ||
          activeAssetRef.current !== assetId
        )
          return;
        setSchedule(result);
        setLoadedFor(assetId);
        setIntervalValue(String(result.interval_value ?? 6));
        setIntervalUnit(result.interval_unit ?? 'months');
        setNextDueDate(result.next_due_date ?? '');
      })
      .catch((reason: unknown) => {
        if (
          mountedRef.current &&
          requestRef.current === request &&
          activeAssetRef.current === assetId
        )
          setError(getErrorDetail(reason) ?? 'Could not load maintenance schedule.');
      })
      .finally(() => {
        if (
          mountedRef.current &&
          requestRef.current === request &&
          activeAssetRef.current === assetId
        )
          setLoading(false);
      });
  }, [assetId, refresh]);

  const current = loadedFor === assetId && !loading ? schedule : null;
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!current || saving) return;
    const value = Number(intervalValue);
    if (!Number.isInteger(value) || value <= 0) {
      setError('Interval must be a positive whole number.');
      return;
    }
    const request = requestRef.current;
    const submittedAssetId = assetId;
    setSaving(true);
    setError(null);
    setCreateConflict(false);
    const operation = current.id
      ? updateMaintenanceSchedule(assetId, {
          interval_value: value,
          interval_unit: intervalUnit,
          next_due_date: nextDueDate || null,
        })
      : createMaintenanceSchedule(assetId, {
          interval_value: value,
          interval_unit: intervalUnit,
          next_due_date: nextDueDate || null,
        });
    void operation
      .then((result) => {
        if (
          !mountedRef.current ||
          requestRef.current !== request ||
          activeAssetRef.current !== submittedAssetId
        )
          return;
        setSchedule(result);
        setNextDueDate(result.next_due_date ?? '');
      })
      .catch((reason: unknown) => {
        if (
          mountedRef.current &&
          requestRef.current === request &&
          activeAssetRef.current === submittedAssetId
        ) {
          setError(getErrorDetail(reason) ?? 'Could not save maintenance schedule.');
          if (!current.id && reason instanceof ApiError && reason.status === 409)
            setCreateConflict(true);
        }
      })
      .finally(() => {
        if (
          mountedRef.current &&
          requestRef.current === request &&
          activeAssetRef.current === submittedAssetId
        )
          setSaving(false);
      });
  };

  const todayUtc = new Date().toISOString().slice(0, 10);
  const dueStatus = current?.next_due_date
    ? current.next_due_date < todayUtc
      ? 'Overdue'
      : current.next_due_date === todayUtc
        ? 'Due today'
        : 'Upcoming'
    : null;

  return (
    <section aria-label="Maintenance schedule">
      <h3>Maintenance schedule</h3>
      {loading && <p role="status">Loading maintenance schedule…</p>}
      {error && <p role="alert">{error}</p>}
      {createConflict && current && !current.id && (
        <button
          type="button"
          className="button"
          onClick={() => {
            setRefresh((value) => value + 1);
          }}
        >
          Reload maintenance schedule
        </button>
      )}
      {current && !current.id && <p>No maintenance schedule yet.</p>}
      {current?.id && (
        <p>
          Current next due date:{' '}
          <time dateTime={current.next_due_date ?? undefined}>
            {current.next_due_date ?? 'Not set'}
          </time>
          {dueStatus ? ` — ${dueStatus}` : ''}
        </p>
      )}
      {current && (
        <form onSubmit={submit} aria-label="Edit maintenance schedule">
          <div className="form-field">
            <label htmlFor="maintenance-interval-value">Interval value</label>
            <input
              id="maintenance-interval-value"
              type="number"
              min="1"
              step="1"
              required
              value={intervalValue}
              onChange={(event) => {
                setIntervalValue(event.target.value);
              }}
            />
          </div>
          <div className="form-field">
            <label htmlFor="maintenance-interval-unit">Interval unit</label>
            <select
              id="maintenance-interval-unit"
              value={intervalUnit}
              onChange={(event) => {
                setIntervalUnit(event.target.value as CalibrationIntervalUnit);
              }}
            >
              <option value="days">Days</option>
              <option value="months">Months</option>
              <option value="years">Years</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="maintenance-due-date">Next due date</label>
            <input
              id="maintenance-due-date"
              type="date"
              value={nextDueDate}
              onChange={(event) => {
                setNextDueDate(event.target.value);
              }}
            />
          </div>
          <button type="submit" className="button button--primary" disabled={saving}>
            {saving
              ? 'Saving…'
              : current.id
                ? 'Save maintenance schedule'
                : 'Create maintenance schedule'}
          </button>
        </form>
      )}
    </section>
  );
}
