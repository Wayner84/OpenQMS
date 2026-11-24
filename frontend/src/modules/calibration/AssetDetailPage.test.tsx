import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listPeople } from '../people/api';
import { deleteAsset, getAsset, updateAsset } from './api';
import { AssetDetailPage } from './AssetDetailPage';

vi.mock('./api');
vi.mock('../people/api');

const asset = {
  id: 'a1',
  organisation_id: 'o1',
  asset_tag: 'CAL-01',
  name: 'Micrometer',
  asset_type: 'measuring_equipment' as const,
  serial_number: 'S123',
  location: 'Lab',
  owner_id: null,
  status: 'in_service' as const,
  purchase_date: '2025-01-10',
  created_by_id: 'u1',
  updated_by_id: 'u1',
};
const person = {
  id: 'p1',
  organisation_id: 'o1',
  company_id: null,
  first_name: 'Ada',
  last_name: 'Lovelace',
  email: null,
  phone: null,
  role: null,
  department: null,
  notes: null,
  is_employee: true,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};
function RouteChange(): React.ReactElement {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => {
        void navigate('/calibration/assets/a2');
      }}
    >
      Other asset
    </button>
  );
}
function renderPage(strict = false): ReturnType<typeof render> {
  const page = (
    <MemoryRouter initialEntries={['/calibration/assets/a1']}>
      <Routes>
        <Route
          path="/calibration/assets/:id"
          element={
            <>
              <RouteChange />
              <AssetDetailPage />
            </>
          }
        />
        <Route path="/calibration/assets" element={<p>Asset register</p>} />
      </Routes>
    </MemoryRouter>
  );
  return render(strict ? <StrictMode>{page}</StrictMode> : page);
}

describe('AssetDetailPage', () => {
  beforeEach(() => {
    vi.mocked(getAsset).mockResolvedValue(asset);
    vi.mocked(listPeople).mockResolvedValue({ items: [person], total: 1, limit: 200, offset: 0 });
  });
  afterEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it('loads asset metadata by route id in StrictMode', async () => {
    renderPage(true);
    expect(await screen.findByText('Micrometer')).toBeInTheDocument();
    expect(getAsset).toHaveBeenCalledWith('a1');
    expect(screen.getByText('CAL-01')).toBeInTheDocument();
  });

  it('edits all metadata with a selected owner without clearing retained fields', async () => {
    vi.mocked(updateAsset).mockResolvedValue({ ...asset, name: 'Caliper', owner_id: 'p1' });
    renderPage();
    await screen.findByRole('option', { name: 'Ada Lovelace' });
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Caliper' } });
    fireEvent.change(screen.getByLabelText(/^owner$/i), { target: { value: 'p1' } });
    fireEvent.click(screen.getByRole('button', { name: /save asset/i }));
    await waitFor(() => {
      expect(updateAsset).toHaveBeenCalledWith('a1', {
        asset_tag: 'CAL-01',
        name: 'Caliper',
        asset_type: 'measuring_equipment',
        serial_number: 'S123',
        location: 'Lab',
        owner_id: 'p1',
        status: 'in_service',
        purchase_date: '2025-01-10',
      });
    });
  });

  it('only soft-deletes after confirmation and returns to register', async () => {
    vi.mocked(deleteAsset).mockResolvedValue(undefined);
    const confirm = vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true);
    vi.stubGlobal('confirm', confirm);
    renderPage();
    await screen.findByText('Micrometer');
    fireEvent.click(screen.getByRole('button', { name: /delete asset/i }));
    expect(deleteAsset).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /delete asset/i }));
    await waitFor(() => {
      expect(deleteAsset).toHaveBeenCalledWith('a1');
    });
    expect(await screen.findByText('Asset register')).toBeInTheDocument();
  });

  it('ignores the older response after navigating to another asset id', async () => {
    let resolveOld!: (result: typeof asset) => void;
    vi.mocked(getAsset)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve;
          }),
      )
      .mockResolvedValueOnce({ ...asset, id: 'a2', name: 'Caliper', asset_tag: 'CAL-02' });
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Other asset' }));
    expect(await screen.findByText('Caliper')).toBeInTheDocument();
    resolveOld(asset);
    await waitFor(() => {
      expect(screen.getByText('Caliper')).toBeInTheDocument();
    });
    expect(screen.queryByText('Micrometer')).not.toBeInTheDocument();
  });
});
