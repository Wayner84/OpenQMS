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
});
