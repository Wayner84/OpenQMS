import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listCompanies } from '../people/api';
import {
  createCertification,
  createPerformanceRecord,
  deleteCertification,
  getSupplier,
  listCertifications,
  listNcrHistory,
  listPerformanceRecords,
  updateCertification,
  updateSupplier,
} from './api';
import { SupplierDetailPage } from './SupplierDetailPage';

vi.mock('./api');
vi.mock('../people/api');

const mockedGetSupplier = vi.mocked(getSupplier);
const mockedUpdateSupplier = vi.mocked(updateSupplier);
const mockedListCertifications = vi.mocked(listCertifications);
const mockedCreateCertification = vi.mocked(createCertification);
const mockedUpdateCertification = vi.mocked(updateCertification);
const mockedDeleteCertification = vi.mocked(deleteCertification);
const mockedListPerformanceRecords = vi.mocked(listPerformanceRecords);
const mockedCreatePerformanceRecord = vi.mocked(createPerformanceRecord);
const mockedListCompanies = vi.mocked(listCompanies);
const mockedListNcrHistory = vi.mocked(listNcrHistory);

const acmeCompany = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Acme Ltd',
  type: 'supplier' as const,
  address: null,
  phone: null,
  general_email: null,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const acmeSupplier = {
  id: 's1',
  organisation_id: 'o1',
  company_id: 'c1',
  approval_status: 'approved' as const,
  risk_rating: 'low' as const,
  is_preferred: true,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const iso9001 = {
  id: 'cert1',
  supplier_id: 's1',
  certification_type: 'ISO 9001',
  certificate_document_id: null,
  issued_date: '2026-01-01',
  expiry_date: '2027-01-01',
};

function renderPage(supplierId = 's1', wrapInStrictMode = false): ReturnType<typeof render> {
  const routes = (
    <MemoryRouter initialEntries={[`/suppliers/${supplierId}`]}>
      <Routes>
        <Route path="/suppliers/:id" element={<SupplierDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
  return render(wrapInStrictMode ? <StrictMode>{routes}</StrictMode> : routes);
}

describe('SupplierDetailPage', () => {
  beforeEach(() => {
    mockedListCompanies.mockResolvedValue({
      items: [acmeCompany],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListCertifications.mockResolvedValue({
      items: [iso9001],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListPerformanceRecords.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListNcrHistory.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedGetSupplier.mockResolvedValue(acmeSupplier);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the supplier metadata and certifications', async () => {
    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Acme Ltd' })).toBeInTheDocument();
    });
    expect(screen.getByText(/approval status: approved/i)).toBeInTheDocument();
    expect(screen.getByText('ISO 9001')).toBeInTheDocument();
  });

  it('loads under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    renderPage('s1', true);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Acme Ltd' })).toBeInTheDocument();
    });
  });

  it('shows an error message when the supplier fails to load', async () => {
    mockedGetSupplier.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load this supplier/i);
  });

  it('edits supplier metadata', async () => {
    mockedUpdateSupplier.mockResolvedValue({ ...acmeSupplier, approval_status: 'suspended' });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Acme Ltd' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit details/i }));
    fireEvent.change(screen.getByLabelText(/approval status/i), {
      target: { value: 'suspended' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mockedUpdateSupplier).toHaveBeenCalledWith(
        's1',
        expect.objectContaining({ approval_status: 'suspended' }),
      );
    });
  });

  it('highlights a certification expiring soon', async () => {
    const soon = new Date();
    soon.setDate(soon.getDate() + 5);
    mockedListCertifications.mockResolvedValue({
      items: [{ ...iso9001, expiry_date: soon.toISOString().slice(0, 10) }],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();

    expect(await screen.findByText(/expiring soon/i)).toBeInTheDocument();
  });

  it('adds a certification', async () => {
    mockedListCertifications.mockResolvedValueOnce({ items: [], total: 0, limit: 200, offset: 0 });
    mockedCreateCertification.mockResolvedValue(iso9001);
    mockedListCertifications.mockResolvedValueOnce({
      items: [iso9001],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/certification type/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/certification type/i), {
      target: { value: 'ISO 9001' },
    });
    fireEvent.click(screen.getByRole('button', { name: /add certification/i }));

    await waitFor(() => {
      expect(mockedCreateCertification).toHaveBeenCalledWith(
        's1',
        expect.objectContaining({ certification_type: 'ISO 9001' }),
      );
    });
  });

  it('edits a certification', async () => {
    mockedUpdateCertification.mockResolvedValue({ ...iso9001, certification_type: 'AS9100' });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('ISO 9001')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit iso 9001/i }));
    fireEvent.change(screen.getByLabelText(/certification type/i), {
      target: { value: 'AS9100' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mockedUpdateCertification).toHaveBeenCalledWith(
        's1',
        'cert1',
        expect.objectContaining({ certification_type: 'AS9100' }),
      );
    });
  });

  it('deletes a certification', async () => {
    mockedDeleteCertification.mockResolvedValue(undefined);

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('ISO 9001')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete iso 9001/i }));

    await waitFor(() => {
      expect(mockedDeleteCertification).toHaveBeenCalledWith('s1', 'cert1');
    });
  });

  it('adds a performance record', async () => {
    mockedCreatePerformanceRecord.mockResolvedValue({
      id: 'p1',
      supplier_id: 's1',
      period: '2026-Q3',
      score: '90.00',
      notes: null,
      created_by_id: 'u1',
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/period/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/period/i), { target: { value: '2026-Q3' } });
    fireEvent.change(screen.getByLabelText(/score/i), { target: { value: '90' } });
    fireEvent.click(screen.getByRole('button', { name: /add performance record/i }));

    await waitFor(() => {
      expect(mockedCreatePerformanceRecord).toHaveBeenCalledWith(
        's1',
        expect.objectContaining({ period: '2026-Q3', score: '90' }),
      );
    });
  });

  it('shows the NCR history linked to this supplier', async () => {
    mockedListNcrHistory.mockResolvedValue({
      items: [
        {
          id: 'n1',
          organisation_id: 'o1',
          number: 'SNCR-0001',
          type: 'supplier',
          product_id: null,
          supplier_id: 's1',
          status: 'open',
          raised_by_id: 'p1',
          description: 'Late delivery of fasteners',
          root_cause_summary: null,
          created_by_id: 'u1',
          updated_by_id: 'u1',
          closed_at: null,
        },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();

    expect(await screen.findByRole('link', { name: 'SNCR-0001' })).toHaveAttribute(
      'href',
      '/ncr/n1',
    );
    expect(screen.getByText('Late delivery of fasteners')).toBeInTheDocument();
  });
});
