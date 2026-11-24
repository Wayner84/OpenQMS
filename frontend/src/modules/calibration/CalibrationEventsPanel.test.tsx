import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import { listDocuments } from '../documents/api';
import { listCompanies, listPeople } from '../people/api';
import { listSuppliers } from '../suppliers/api';
import { createCalibrationEvent, listCalibrationEvents } from './api';
import { CalibrationEventsPanel } from './CalibrationEventsPanel';

vi.mock('./api');
vi.mock('../people/api');
vi.mock('../suppliers/api');
vi.mock('../documents/api');
const event = {
  id: 'e1',
  asset_id: 'a1',
  performed_at: '2026-11-20',
  performed_by_id: null,
  performed_by_supplier_id: 's1',
  certificate_document_id: 'd1',
  result: 'pass' as const,
  notes: 'Done',
  next_due_date: '2027-11-20',
  created_by_id: 'u1',
};
const empty = { items: [], total: 0, limit: 20, offset: 0 };
const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 200, offset: 0 });
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
const company = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Acme Calibration',
  type: 'supplier' as const,
  address: null,
  phone: null,
  general_email: null,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};
const supplier = {
  id: 's1',
  organisation_id: 'o1',
  company_id: 'c1',
  approval_status: 'approved' as const,
  risk_rating: null,
  is_preferred: false,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};
const document = {
  id: 'd1',
  organisation_id: 'o1',
  category_id: null,
  number: 'CERT-001',
  title: 'Calibration certificate',
  owner_id: null,
  status: 'approved' as const,
  current_version_id: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
  tags: [],
};

describe('CalibrationEventsPanel', () => {
  beforeEach(() => {
    vi.mocked(listCalibrationEvents).mockResolvedValue({ ...empty, items: [event], total: 1 });
    vi.mocked(listPeople).mockResolvedValue(page([person]));
    vi.mocked(listCompanies).mockResolvedValue(page([company]));
    vi.mocked(listSuppliers).mockResolvedValue(page([supplier]));
    vi.mocked(listDocuments).mockResolvedValue(page([document]));
  });
  afterEach(() => vi.resetAllMocks());

  it('shows immutable history and a named supplier and linked certificate', async () => {
    render(
      <StrictMode>
        <CalibrationEventsPanel assetId="a1" />
      </StrictMode>,
      { wrapper: MemoryRouter },
    );
    expect(await screen.findByText('2026-11-20')).toBeInTheDocument();
    expect(await screen.findByText(/Acme Calibration/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /CERT-001/ })).toHaveAttribute('href', '/documents/d1');
    expect(screen.getByText(/2027-11-20/)).toBeInTheDocument();
  });

  it('records an external calibration with a certificate and refreshes history', async () => {
    vi.mocked(listCalibrationEvents)
      .mockResolvedValueOnce(empty)
      .mockResolvedValueOnce({ ...empty, items: [event], total: 1 });
    vi.mocked(createCalibrationEvent).mockResolvedValue(event);
    render(<CalibrationEventsPanel assetId="a1" />, { wrapper: MemoryRouter });
    await screen.findByRole('option', { name: /CERT-001/ });
    fireEvent.change(screen.getByLabelText(/performed at/i), { target: { value: '2026-11-20' } });
    fireEvent.change(screen.getByLabelText(/performer type/i), { target: { value: 'supplier' } });
    await screen.findByRole('option', { name: /Acme Calibration/ });
    fireEvent.change(screen.getByLabelText(/supplier$/i), { target: { value: 's1' } });
    fireEvent.change(screen.getByLabelText(/certificate document/i), { target: { value: 'd1' } });
    fireEvent.change(screen.getByLabelText(/^notes$/i), { target: { value: 'Done' } });
    fireEvent.click(screen.getByRole('button', { name: /record calibration/i }));
    await waitFor(() => {
      expect(createCalibrationEvent).toHaveBeenCalledWith('a1', {
        performed_at: '2026-11-20',
        performed_by_id: null,
        performed_by_supplier_id: 's1',
        certificate_document_id: 'd1',
        result: 'pass',
        notes: 'Done',
      });
    });
    expect(await screen.findByText('2026-11-20')).toBeInTheDocument();
  });

  it('requires a selected person for in-house calibration and never sends both performer fields', async () => {
    vi.mocked(createCalibrationEvent).mockResolvedValue({
      ...event,
      performed_by_id: 'p1',
      performed_by_supplier_id: null,
    });
    render(<CalibrationEventsPanel assetId="a1" />, { wrapper: MemoryRouter });
    await screen.findByRole('option', { name: /CERT-001/ });
    fireEvent.change(screen.getByLabelText(/performed at/i), { target: { value: '2026-11-20' } });
    fireEvent.change(screen.getByLabelText(/performer type/i), { target: { value: 'person' } });
    await screen.findByRole('option', { name: 'Ada Lovelace' });
    fireEvent.click(screen.getByRole('button', { name: /record calibration/i }));
    expect(createCalibrationEvent).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/person$/i), { target: { value: 'p1' } });
    fireEvent.click(screen.getByRole('button', { name: /record calibration/i }));
    await waitFor(() => {
      expect(createCalibrationEvent).toHaveBeenCalledWith(
        'a1',
        expect.objectContaining({ performed_by_id: 'p1', performed_by_supplier_id: null }),
      );
    });
  });

  it('blocks recording when picker data fails and offers retry', async () => {
    vi.mocked(listDocuments).mockRejectedValueOnce(new Error('offline'));
    render(<CalibrationEventsPanel assetId="a1" />, { wrapper: MemoryRouter });
    expect(await screen.findByRole('alert')).toHaveTextContent(/options/i);
    expect(screen.getByRole('button', { name: /record calibration/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /retry options/i }));
    expect(await screen.findByRole('option', { name: /CERT-001/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /record calibration/i })).toBeEnabled();
  });

  it('paginates history and ignores an older asset response after switching', async () => {
    let resolveOld!: (value: typeof empty) => void;
    vi.mocked(listCalibrationEvents)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve;
          }),
      )
      .mockResolvedValueOnce({
        ...empty,
        items: [{ ...event, asset_id: 'a2', id: 'e2', performed_at: '2026-11-21' }],
        total: 21,
      });
    const { rerender } = render(<CalibrationEventsPanel assetId="a1" />, { wrapper: MemoryRouter });
    rerender(<CalibrationEventsPanel assetId="a2" />);
    expect(await screen.findByText('2026-11-21')).toBeInTheDocument();
    await act(async () => {
      resolveOld(empty);
      await Promise.resolve();
    });
    expect(screen.getByText('2026-11-21')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next events' }));
    await waitFor(() => {
      expect(listCalibrationEvents).toHaveBeenLastCalledWith('a2', { limit: 20, offset: 20 });
    });
  });

  it('shows a 404 without offering event creation for a missing asset', async () => {
    vi.mocked(listCalibrationEvents).mockRejectedValue(
      new ApiError('missing', 404, { detail: 'Asset not found' }),
    );
    render(<CalibrationEventsPanel assetId="a1" />, { wrapper: MemoryRouter });
    expect(await screen.findByRole('alert')).toHaveTextContent('Asset not found');
    expect(screen.queryByRole('button', { name: /record calibration/i })).not.toBeInTheDocument();
  });

  it('keeps navigation disabled during a pending record and permits retry after failure', async () => {
    vi.mocked(listCalibrationEvents).mockResolvedValue({ ...empty, items: [event], total: 21 });
    let rejectWrite!: (reason: Error) => void;
    vi.mocked(createCalibrationEvent).mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectWrite = reject;
        }),
    );
    render(<CalibrationEventsPanel assetId="a1" />, { wrapper: MemoryRouter });
    await screen.findByRole('option', { name: /CERT-001/ });
    fireEvent.change(screen.getByLabelText(/performed at/i), { target: { value: '2026-11-20' } });
    fireEvent.click(screen.getByRole('button', { name: /record calibration/i }));
    expect(screen.getByRole('button', { name: 'Next events' })).toBeDisabled();
    await act(async () => {
      rejectWrite(new Error('offline'));
      await Promise.resolve();
    });
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not record/i);
    expect(screen.getByRole('button', { name: 'Next events' })).toBeEnabled();
    vi.mocked(createCalibrationEvent).mockResolvedValueOnce(event);
    fireEvent.click(screen.getByRole('button', { name: /record calibration/i }));
    await waitFor(() => {
      expect(createCalibrationEvent).toHaveBeenCalledTimes(2);
    });
  });

  it('can refresh certificate options after a new document is uploaded', async () => {
    vi.mocked(listDocuments)
      .mockResolvedValueOnce(page([]))
      .mockResolvedValueOnce(page([document]));
    render(<CalibrationEventsPanel assetId="a1" />, { wrapper: MemoryRouter });
    await screen.findByText('2026-11-20');
    expect(screen.queryByRole('option', { name: /CERT-001/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /refresh options/i }));
    expect(await screen.findByRole('option', { name: /CERT-001/ })).toBeInTheDocument();
  });
});
