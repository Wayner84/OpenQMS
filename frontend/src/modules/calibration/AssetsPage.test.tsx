import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createAsset, listAssets } from './api';
import { AssetsPage } from './AssetsPage';
import { listPeople } from '../../modules/people/api';

vi.mock('./api');
vi.mock('../../modules/people/api');

const asset = {
  id: 'a1',
  organisation_id: 'o1',
  asset_tag: 'CAL-01',
  name: 'Micrometer',
  asset_type: 'measuring_equipment' as const,
  serial_number: null,
  location: 'Lab A',
  owner_id: 'p1',
  status: 'in_service' as const,
  purchase_date: null,
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
const page = { items: [asset], total: 1, limit: 20, offset: 0 };
const mockedList = vi.mocked(listAssets);

function renderPage(strict = false): ReturnType<typeof render> {
  const content = (
    <MemoryRouter>
      <AssetsPage />
    </MemoryRouter>
  );
  return render(strict ? <StrictMode>{content}</StrictMode> : content);
}

describe('AssetsPage', () => {
  beforeEach(() => {
    mockedList.mockResolvedValue(page);
    vi.mocked(listPeople).mockResolvedValue({ items: [person], total: 1, limit: 200, offset: 0 });
  });
  afterEach(() => vi.resetAllMocks());

  it('loads assets and owner options in StrictMode', async () => {
    renderPage(true);
    expect(await screen.findByText('Micrometer')).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: 'Ada Lovelace' })).toBeInTheDocument();
  });

  it('sends search and asset type, status, and location filters', async () => {
    renderPage();
    await screen.findByText('Micrometer');
    const initialCalls = mockedList.mock.calls.length;
    fireEvent.change(screen.getByLabelText(/filter by type/i), {
      target: { value: 'measuring_equipment' },
    });
    fireEvent.change(screen.getByLabelText(/filter by status/i), {
      target: { value: 'in_service' },
    });
    fireEvent.change(screen.getByLabelText(/filter by location/i), { target: { value: 'Lab A' } });
    fireEvent.change(screen.getByLabelText(/^search$/i), { target: { value: 'mic' } });
    expect(mockedList).toHaveBeenCalledTimes(initialCalls);
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));
    await waitFor(() => {
      expect(mockedList).toHaveBeenLastCalledWith(
        expect.objectContaining({
          search: 'mic',
          assetType: 'measuring_equipment',
          status: 'in_service',
          location: 'Lab A',
        }),
      );
    });
  });

  it('creates an asset with the selected People owner and refreshes the list', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Ada Lovelace' });
    fireEvent.change(screen.getByLabelText(/asset tag/i), { target: { value: 'CAL-02' } });
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Caliper' } });
    fireEvent.change(screen.getByLabelText(/owner/i), { target: { value: 'p1' } });
    vi.mocked(createAsset).mockResolvedValue(asset);
    fireEvent.click(screen.getByRole('button', { name: /create asset/i }));
    await waitFor(() => {
      expect(createAsset).toHaveBeenCalledWith(
        expect.objectContaining({ asset_tag: 'CAL-02', name: 'Caliper', owner_id: 'p1' }),
      );
    });
    expect(await screen.findByText('Micrometer')).toBeInTheDocument();
  });

  it('keeps the latest filtered response when requests resolve out of order', async () => {
    let resolveOlder!: (value: typeof page) => void;
    mockedList
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOlder = resolve;
          }),
      )
      .mockResolvedValueOnce({ ...page, items: [{ ...asset, id: 'a2', name: 'Current result' }] });
    renderPage();
    fireEvent.change(screen.getByLabelText(/^search$/i), { target: { value: 'new' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));
    expect(await screen.findByText('Current result')).toBeInTheDocument();
    resolveOlder(page);
    await waitFor(() => {
      expect(screen.getByText('Current result')).toBeInTheDocument();
    });
    expect(screen.queryByText('Micrometer')).not.toBeInTheDocument();
  });

  it('paginates beyond the first 20 assets', async () => {
    mockedList.mockResolvedValueOnce({ ...page, total: 21 }).mockResolvedValueOnce({
      ...page,
      items: [{ ...asset, id: 'a21', name: 'Last asset' }],
      total: 21,
      offset: 20,
    });
    renderPage();
    await screen.findByText('Micrometer');
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(await screen.findByText('Last asset')).toBeInTheDocument();
    expect(mockedList).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 20, offset: 20 }));
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /previous/i }));
    expect(await screen.findByText('Micrometer')).toBeInTheDocument();
    expect(mockedList).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 0 }));
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
  });

  it('does not use owner options from an obsolete StrictMode request', async () => {
    let resolveOlder!: (value: Awaited<ReturnType<typeof listPeople>>) => void;
    vi.mocked(listPeople)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOlder = resolve;
          }),
      )
      .mockResolvedValueOnce({ items: [person], total: 1, limit: 200, offset: 0 });
    renderPage(true);
    expect(await screen.findByRole('option', { name: 'Ada Lovelace' })).toBeInTheDocument();
    await act(async () => {
      resolveOlder({
        items: [{ ...person, id: 'p2', first_name: 'Old' }],
        total: 1,
        limit: 200,
        offset: 0,
      });
      await Promise.resolve();
    });
    expect(screen.queryByRole('option', { name: 'Old Lovelace' })).not.toBeInTheDocument();
  });

  it('resets pagination when submitting a new filter', async () => {
    mockedList.mockResolvedValueOnce({ ...page, total: 21 }).mockResolvedValueOnce({
      ...page,
      items: [{ ...asset, id: 'a21', name: 'Last asset' }],
      total: 21,
      offset: 20,
    });
    renderPage();
    await screen.findByText('Micrometer');
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    await screen.findByText('Last asset');
    fireEvent.change(screen.getByLabelText(/filter by type/i), {
      target: { value: 'company_asset' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));
    await waitFor(() => {
      expect(mockedList).toHaveBeenLastCalledWith(
        expect.objectContaining({ assetType: 'company_asset', offset: 0 }),
      );
    });
  });

  it('does not allow creation before owner options load and offers retry on failure', async () => {
    vi.mocked(listPeople).mockRejectedValueOnce(new Error('offline'));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load asset owners');
    expect(screen.getByRole('button', { name: /^create asset$/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /retry owners/i }));
    expect(await screen.findByRole('option', { name: 'Ada Lovelace' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^create asset$/i })).toBeEnabled();
  });
});
