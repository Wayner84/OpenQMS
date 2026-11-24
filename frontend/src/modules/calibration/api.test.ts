import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiDelete, apiGet, apiPatch, apiPost } from '../../shared/api/client';
import {
  createAsset,
  createCalibrationSchedule,
  deleteAsset,
  getAsset,
  getCalibrationSchedule,
  listAssets,
  updateAsset,
  updateCalibrationSchedule,
  getMaintenanceSchedule,
  createMaintenanceSchedule,
  updateMaintenanceSchedule,
  listDue,
  listCalibrationEvents,
  createCalibrationEvent,
} from './api';

vi.mock('../../shared/api/client');

describe('calibration asset API', () => {
  beforeEach(() => vi.resetAllMocks());

  it('serializes all asset filters and pagination to the calibration endpoint', async () => {
    vi.mocked(apiGet).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    await listAssets({
      assetType: 'measuring_equipment',
      status: 'in_service',
      location: 'Lab A',
      search: 'mic',
      limit: 20,
      offset: 0,
    });
    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/calibration/assets?asset_type=measuring_equipment&status=in_service&location=Lab+A&search=mic&limit=20&offset=0',
    );
  });

  it('posts the typed asset payload to the calibration endpoint', async () => {
    vi.mocked(apiPost).mockResolvedValue({});
    const payload = {
      asset_tag: 'CAL-01',
      name: 'Micrometer',
      asset_type: 'measuring_equipment' as const,
      owner_id: 'person-1',
    };
    await createAsset(payload);
    expect(apiPost).toHaveBeenCalledWith('/api/v1/calibration/assets', payload);
  });

  it('reads, updates and soft-deletes an asset by id', async () => {
    vi.mocked(apiGet).mockResolvedValue({ id: 'a1' });
    vi.mocked(apiPatch).mockResolvedValue({ id: 'a1' });
    vi.mocked(apiDelete).mockResolvedValue(undefined);
    const payload = {
      asset_tag: 'CAL-01',
      name: 'Micrometer',
      asset_type: 'measuring_equipment' as const,
    };
    await getAsset('a1');
    await updateAsset('a1', payload);
    await deleteAsset('a1');
    expect(apiGet).toHaveBeenCalledWith('/api/v1/calibration/assets/a1');
    expect(apiPatch).toHaveBeenCalledWith('/api/v1/calibration/assets/a1', payload);
    expect(apiDelete).toHaveBeenCalledWith('/api/v1/calibration/assets/a1');
  });

  it('reads, creates and updates a calibration schedule via its asset', async () => {
    vi.mocked(apiGet).mockResolvedValue({});
    vi.mocked(apiPost).mockResolvedValue({});
    vi.mocked(apiPatch).mockResolvedValue({});
    await getCalibrationSchedule('a1');
    await createCalibrationSchedule('a1', { interval_value: 12, interval_unit: 'months' });
    await updateCalibrationSchedule('a1', {
      interval_value: 1,
      interval_unit: 'years',
      next_due_date: '2027-01-01',
    });
    expect(apiGet).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/schedule');
    expect(apiPost).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/schedule', {
      interval_value: 12,
      interval_unit: 'months',
    });
    expect(apiPatch).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/schedule', {
      interval_value: 1,
      interval_unit: 'years',
      next_due_date: '2027-01-01',
    });
  });

  it('reads, creates and partially updates equipment maintenance schedules', async () => {
    vi.mocked(apiGet).mockResolvedValue({});
    vi.mocked(apiPost).mockResolvedValue({});
    vi.mocked(apiPatch).mockResolvedValue({});
    await getMaintenanceSchedule('a1');
    await createMaintenanceSchedule('a1', {
      interval_value: 1,
      interval_unit: 'years',
      next_due_date: '2027-01-01',
    });
    await updateMaintenanceSchedule('a1', { next_due_date: null });
    expect(apiGet).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/maintenance-schedule');
    expect(apiPost).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/maintenance-schedule', {
      interval_value: 1,
      interval_unit: 'years',
      next_due_date: '2027-01-01',
    });
    expect(apiPatch).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/maintenance-schedule', {
      next_due_date: null,
    });
  });

  it('requests due entries with an optional window and bounded page parameters', async () => {
    vi.mocked(apiGet).mockResolvedValue({});
    await listDue({ limit: 20, offset: 0 });
    await listDue({ withinDays: 14, limit: 20, offset: 20 });
    expect(apiGet).toHaveBeenCalledWith('/api/v1/calibration/due?limit=20&offset=0');
    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/calibration/due?within_days=14&limit=20&offset=20',
    );
  });

  it('lists and records immutable calibration events for an asset', async () => {
    vi.mocked(apiGet).mockResolvedValue({});
    vi.mocked(apiPost).mockResolvedValue({});
    await listCalibrationEvents('a1', { limit: 20, offset: 20 });
    const payload = {
      performed_at: '2026-11-24',
      performed_by_id: null,
      performed_by_supplier_id: 's1',
      certificate_document_id: 'd1',
      result: 'pass' as const,
      notes: 'Certificate received',
    };
    await createCalibrationEvent('a1', payload);
    expect(apiGet).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/events?limit=20&offset=20');
    expect(apiPost).toHaveBeenCalledWith('/api/v1/calibration/assets/a1/events', payload);
  });
});
