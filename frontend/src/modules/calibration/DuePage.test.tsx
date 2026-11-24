import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listDue } from './api';
import { DuePage } from './DuePage';

vi.mock('./api');
const response = {
  items: [
    {
      asset_id: 'a1',
      asset_tag: 'CAL-01',
      asset_name: 'Micrometer',
      due_type: 'calibration' as const,
      next_due_date: '2026-11-20',
    },
    {
      asset_id: 'a1',
      asset_tag: 'CAL-01',
      asset_name: 'Micrometer',
      due_type: 'maintenance' as const,
      next_due_date: '2026-12-01',
    },
  ],
  total: 2,
  limit: 20,
  offset: 0,
  within_days: 30,
};
const first = response.items[0];
if (!first) throw new Error('Due test fixture is missing its first item');
const renderPage = (strict = false): ReturnType<typeof render> =>
  render(
    <MemoryRouter>
      {strict ? (
        <StrictMode>
          <DuePage />
        </StrictMode>
      ) : (
        <DuePage />
      )}
    </MemoryRouter>,
  );

describe('DuePage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(listDue).mockResolvedValue(response);
  });

  it('shows both obligations for one asset and links to its details', async () => {
    renderPage(true);
    expect(await screen.findByText('Calibration')).toBeInTheDocument();
    expect(screen.getByText('Maintenance')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /CAL-01/i })).toHaveLength(2);
    expect(screen.getAllByRole('link', { name: /CAL-01/i })[0]).toHaveAttribute(
      'href',
      '/calibration/assets/a1',
    );
    expect(screen.getByText(/30 days/i)).toBeInTheDocument();
    expect(listDue).toHaveBeenCalledWith({ limit: 20, offset: 0 });
  });

  it('applies a bounded window only when submitted and resets pagination', async () => {
    renderPage();
    await screen.findByText('Calibration');
    fireEvent.change(screen.getByLabelText(/within days/i), { target: { value: '14' } });
    expect(listDue).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: /apply window/i }));
    await waitFor(() => {
      expect(listDue).toHaveBeenLastCalledWith({ withinDays: 14, limit: 20, offset: 0 });
    });
    fireEvent.change(screen.getByLabelText(/within days/i), { target: { value: '3651' } });
    fireEvent.click(screen.getByRole('button', { name: /apply window/i }));
    expect(listDue).toHaveBeenCalledTimes(2);
  });

  it('uses the singular day label for a one-day window', async () => {
    vi.mocked(listDue).mockResolvedValue({ ...response, within_days: 1 });
    renderPage();
    expect(await screen.findByText(/within 1 day\)/i)).toBeInTheDocument();
  });

  it('paginates all matching entries, not only the first 20', async () => {
    vi.mocked(listDue)
      .mockResolvedValueOnce({ ...response, total: 21 })
      .mockResolvedValueOnce({
        ...response,
        items: [{ ...first, asset_id: 'a2', asset_tag: 'CAL-21' }],
        total: 21,
        offset: 20,
      });
    renderPage();
    await screen.findByText('Calibration');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('link', { name: /CAL-21/i })).toHaveAttribute(
      'href',
      '/calibration/assets/a2',
    );
    expect(listDue).toHaveBeenLastCalledWith({ limit: 20, offset: 20 });
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  });

  it('ignores older responses after changing the window', async () => {
    let resolveOld!: (value: typeof response) => void;
    vi.mocked(listDue)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve;
          }),
      )
      .mockResolvedValueOnce({ ...response, items: [{ ...first, asset_tag: 'NEW' }] });
    renderPage();
    fireEvent.change(screen.getByLabelText(/within days/i), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: /apply window/i }));
    expect(await screen.findByRole('link', { name: /NEW/i })).toBeInTheDocument();
    await act(async () => {
      resolveOld(response);
      await Promise.resolve();
    });
    expect(screen.queryByRole('link', { name: /CAL-01/i })).not.toBeInTheDocument();
  });

  it('shows errors and permits a retry', async () => {
    vi.mocked(listDue).mockRejectedValueOnce(new Error('offline'));
    renderPage();
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByText('Calibration')).toBeInTheDocument();
  });
});
