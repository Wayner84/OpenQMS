import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiGet, apiPost } from '../../shared/api/client';
import { createAsset, listAssets } from './api';

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
});
