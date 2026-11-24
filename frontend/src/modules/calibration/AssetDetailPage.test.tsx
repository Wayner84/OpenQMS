import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listCompanies, listPeople } from '../people/api';
import { listDocuments } from '../documents/api';
import { listSuppliers } from '../suppliers/api';
import {
  createCalibrationEvent,
  deleteAsset,
  getAsset,
  getCalibrationSchedule,
  getMaintenanceSchedule,
  listCalibrationEvents,
  updateAsset,
} from './api';
import { AssetDetailPage } from './AssetDetailPage';

vi.mock('./api');
vi.mock('../people/api');
vi.mock('../documents/api');
vi.mock('../suppliers/api');

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
    vi.mocked(getCalibrationSchedule).mockResolvedValue({
      id: 's1',
      asset_id: 'a1',
      interval_value: 12,
      interval_unit: 'months',
      next_due_date: '2027-04-10',
      created_by_id: 'u1',
      updated_by_id: 'u1',
    });
    vi.mocked(listPeople).mockResolvedValue({ items: [person], total: 1, limit: 200, offset: 0 });
    vi.mocked(listCompanies).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    vi.mocked(listSuppliers).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    vi.mocked(listDocuments).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    vi.mocked(listCalibrationEvents).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
    vi.mocked(getMaintenanceSchedule).mockResolvedValue({
      id: null,
      asset_id: 'a1',
      interval_value: null,
      interval_unit: null,
      next_due_date: null,
      created_by_id: null,
      updated_by_id: null,
    });
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
    expect(await screen.findByText('2027-04-10')).toBeInTheDocument();
    expect(await screen.findByText(/no maintenance schedule yet/i)).toBeInTheDocument();
    expect(await screen.findByText(/no calibration events yet/i)).toBeInTheDocument();
  });

  it('refreshes the calibration due date after recording an event', async () => {
    vi.mocked(createCalibrationEvent).mockResolvedValue({
      id: 'e1',
      asset_id: 'a1',
      performed_at: '2026-11-20',
      performed_by_id: null,
      performed_by_supplier_id: null,
      certificate_document_id: null,
      result: 'pass',
      notes: null,
      next_due_date: '2027-11-20',
      created_by_id: 'u1',
    });
    vi.mocked(getCalibrationSchedule)
      .mockResolvedValueOnce({
        id: 's1',
        asset_id: 'a1',
        interval_value: 12,
        interval_unit: 'months',
        next_due_date: '2027-04-10',
        created_by_id: 'u1',
        updated_by_id: 'u1',
      })
      .mockResolvedValueOnce({
        id: 's1',
        asset_id: 'a1',
        interval_value: 12,
        interval_unit: 'months',
        next_due_date: '2027-11-20',
        created_by_id: 'u1',
        updated_by_id: 'u1',
      });
    renderPage();
    await screen.findByText(/no calibration events yet/i);
    fireEvent.change(screen.getByLabelText(/performed at/i), { target: { value: '2026-11-20' } });
    fireEvent.click(screen.getByRole('button', { name: /record calibration/i }));
    await waitFor(() => {
      expect(getCalibrationSchedule).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText('2027-11-20')).toBeInTheDocument();
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
