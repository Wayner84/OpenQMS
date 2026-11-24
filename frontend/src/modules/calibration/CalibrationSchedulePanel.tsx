import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';

import { ApiError, getErrorDetail } from '../../shared/api/client';
import {
  createCalibrationSchedule,
  getCalibrationSchedule,
  updateCalibrationSchedule,
} from './api';
import type { CalibrationIntervalUnit, CalibrationSchedule } from './types';

/** Calibration interval and current due date for one asset. */
export function CalibrationSchedulePanel({ assetId }: { assetId: string }): ReactElement {
  const [schedule, setSchedule] = useState<CalibrationSchedule | null>(null);
  const [missing, setMissing] = useState(false);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [intervalValue, setIntervalValue] = useState('12');
  const [intervalUnit, setIntervalUnit] = useState<CalibrationIntervalUnit>('months');
  const [nextDueDate, setNextDueDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const requestRef = useRef(0);
  const activeAssetRef = useRef(assetId);

  // A write can finish after the new ID commits but before its passive read
  // effect increments requestRef. Invalidate it at layout commit instead.
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
    setMissing(false);
    setLoadedFor(null);
    setError(null);
    setLoading(true);
    setSaving(false);
    void getCalibrationSchedule(assetId)
      .then((result) => {
        if (!mountedRef.current || requestRef.current !== request) return;
        setSchedule(result);
        setIntervalValue(String(result.interval_value));
        setLoadedFor(assetId);
        setIntervalUnit(result.interval_unit);
        setNextDueDate(result.next_due_date ?? '');
      })
      .catch((reason: unknown) => {
        if (!mountedRef.current || requestRef.current !== request) return;
        if (
          reason instanceof ApiError &&
          reason.status === 404 &&
          getErrorDetail(reason)?.includes('has no calibration schedule')
        ) {
          setMissing(true);
          setLoadedFor(assetId);
        } else {
          setError(getErrorDetail(reason) ?? 'Could not load calibration schedule.');
        }
      })
      .finally(() => {
        if (mountedRef.current && requestRef.current === request) setLoading(false);
      });
  }, [assetId]);

  // Props can change before the passive effect runs; never submit an old
  // schedule under the new asset ID.
  const currentSchedule = loadedFor === assetId && !loading ? schedule : null;
  const currentMissing = loadedFor === assetId && !loading && missing;

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!currentSchedule && !currentMissing) return;
    const request = requestRef.current;
    const submittedAssetId = assetId;
    const value = Number(intervalValue);
    if (!Number.isInteger(value) || value <= 0) {
      setError('Interval must be a positive whole number.');
      return;
    }
    if (currentSchedule?.next_due_date && !nextDueDate) {
      setError('Clearing the due date is not supported; set a new date instead.');
      return;
    }
    setSaving(true);
    setError(null);
    const operation = currentSchedule
      ? updateCalibrationSchedule(assetId, {
          interval_value: value,
          interval_unit: intervalUnit,
          next_due_date: nextDueDate || null,
        })
      : createCalibrationSchedule(assetId, { interval_value: value, interval_unit: intervalUnit });
    void operation
      .then((result) => {
        if (
          !mountedRef.current ||
          requestRef.current !== request ||
          activeAssetRef.current !== submittedAssetId
        )
          return;
        setSchedule(result);
        setMissing(false);
        setNextDueDate(result.next_due_date ?? '');
      })
      .catch((reason: unknown) => {
        if (
          mountedRef.current &&
          requestRef.current === request &&
          activeAssetRef.current === submittedAssetId
        )
          setError(getErrorDetail(reason) ?? 'Could not save calibration schedule.');
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
  const dueStatus = currentSchedule?.next_due_date
    ? currentSchedule.next_due_date < todayUtc
      ? 'Overdue'
      : currentSchedule.next_due_date === todayUtc
        ? 'Due today'
        : 'Upcoming'
    : null;

  return (
    <section aria-label="Calibration schedule">
      <h3>Calibration schedule</h3>
      {loading && <p role="status">Loading calibration schedule…</p>}
      {error && <p role="alert">{error}</p>}
      {currentMissing && <p>No calibration schedule yet.</p>}
      {currentSchedule && (
        <p>
          Current next due date:{' '}
          <time dateTime={currentSchedule.next_due_date ?? undefined}>
            {currentSchedule.next_due_date ?? 'Not set'}
          </time>
          {dueStatus ? ` — ${dueStatus}` : ''}
        </p>
      )}
      {(currentSchedule || currentMissing) && (
        <form onSubmit={submit} aria-label="Edit calibration schedule">
          <div className="form-field">
            <label htmlFor="calibration-interval-value">Interval value</label>
            <input
              id="calibration-interval-value"
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
            <label htmlFor="calibration-interval-unit">Interval unit</label>
            <select
              id="calibration-interval-unit"
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
          {currentSchedule && (
            <div className="form-field">
              <label htmlFor="calibration-due-date">Next due date</label>
              <input
                id="calibration-due-date"
                type="date"
                value={nextDueDate}
                onChange={(event) => {
                  setNextDueDate(event.target.value);
                }}
              />
            </div>
          )}
          <button type="submit" className="button button--primary" disabled={saving}>
            {saving ? 'Saving…' : currentSchedule ? 'Save schedule' : 'Create schedule'}
          </button>
        </form>
      )}
    </section>
  );
}
