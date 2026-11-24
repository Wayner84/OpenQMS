import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import {
  createMaintenanceSchedule,
  getMaintenanceSchedule,
  updateMaintenanceSchedule,
} from './api';
import { MaintenanceSchedulePanel } from './MaintenanceSchedulePanel';

vi.mock('./api');
const schedule = {
  id: 's1',
  asset_id: 'a1',
  interval_value: 6,
  interval_unit: 'months' as const,
  next_due_date: '2027-04-10',
  created_by_id: 'u1',
  updated_by_id: 'u1',
};
const empty = {
  id: null,
  asset_id: 'a1',
  interval_value: null,
  interval_unit: null,
  next_due_date: null,
  created_by_id: null,
  updated_by_id: null,
};

describe('MaintenanceSchedulePanel', () => {
  beforeEach(() => vi.mocked(getMaintenanceSchedule).mockResolvedValue(schedule));
  afterEach(() => vi.resetAllMocks());

  it('creates a missing schedule from an empty GET response, including due date', async () => {
    vi.mocked(getMaintenanceSchedule).mockResolvedValue(empty);
    vi.mocked(createMaintenanceSchedule).mockResolvedValue(schedule);
    render(<MaintenanceSchedulePanel assetId="a1" />);
    expect(await screen.findByText(/no maintenance schedule yet/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/next due date/i), { target: { value: '2027-04-10' } });
    fireEvent.click(screen.getByRole('button', { name: /create maintenance schedule/i }));
    await waitFor(() => {
      expect(createMaintenanceSchedule).toHaveBeenCalledWith('a1', {
        interval_value: 6,
        interval_unit: 'months',
        next_due_date: '2027-04-10',
      });
    });
    expect(await screen.findByText(/current next due date/i)).toHaveTextContent('2027-04-10');
  });

  it('patches interval and explicitly clears a due date', async () => {
    vi.mocked(updateMaintenanceSchedule).mockResolvedValue({
      ...schedule,
      interval_value: 1,
      next_due_date: null,
    });
    render(<MaintenanceSchedulePanel assetId="a1" />);
    expect(await screen.findByText(/current next due date/i)).toHaveTextContent('2027-04-10');
    fireEvent.change(screen.getByLabelText(/interval value/i), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText(/next due date/i), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /save maintenance schedule/i }));
    await waitFor(() => {
      expect(updateMaintenanceSchedule).toHaveBeenCalledWith('a1', {
        interval_value: 1,
        interval_unit: 'months',
        next_due_date: null,
      });
    });
    expect(await screen.findByText(/current next due date/i)).toHaveTextContent('Not set');
  });

  it('does not create when asset GET returns 404', async () => {
    vi.mocked(getMaintenanceSchedule).mockRejectedValue(
      new ApiError('missing', 404, { detail: 'Asset not found' }),
    );
    render(<MaintenanceSchedulePanel assetId="a1" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Asset not found');
    expect(
      screen.queryByRole('button', { name: /create maintenance schedule/i }),
    ).not.toBeInTheDocument();
  });

  it('settles after StrictMode effect replay', async () => {
    render(
      <StrictMode>
        <MaintenanceSchedulePanel assetId="a1" />
      </StrictMode>,
    );
    expect(await screen.findByText(/current next due date/i)).toHaveTextContent('2027-04-10');
  });

  it('does not display old asset controls or accept an old write after asset switch', async () => {
    let resolveOld!: (value: typeof schedule) => void;
    vi.mocked(updateMaintenanceSchedule).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    );
    vi.mocked(getMaintenanceSchedule)
      .mockResolvedValueOnce(schedule)
      .mockResolvedValueOnce({ ...empty, asset_id: 'a2' });
    const { rerender } = render(<MaintenanceSchedulePanel assetId="a1" />);
    await screen.findByText(/current next due date/i);
    fireEvent.click(screen.getByRole('button', { name: /save maintenance schedule/i }));
    rerender(<MaintenanceSchedulePanel assetId="a2" />);
    expect(screen.queryByText(/2027-04-10/)).not.toBeInTheDocument();
    expect(await screen.findByText(/no maintenance schedule yet/i)).toBeInTheDocument();
    await act(async () => {
      resolveOld(schedule);
      await Promise.resolve();
    });
    expect(screen.getByText(/no maintenance schedule yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/2027-04-10/)).not.toBeInTheDocument();
  });

  it('shows save errors without pretending to update the schedule', async () => {
    vi.mocked(updateMaintenanceSchedule).mockRejectedValue(
      new ApiError('failure', 409, { detail: 'Conflict' }),
    );
    render(<MaintenanceSchedulePanel assetId="a1" />);
    await screen.findByText(/current next due date/i);
    fireEvent.click(screen.getByRole('button', { name: /save maintenance schedule/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Conflict');
    expect(screen.getByText(/current next due date/i)).toHaveTextContent('2027-04-10');
    expect(screen.getByRole('button', { name: /save maintenance schedule/i })).toBeEnabled();
    vi.mocked(updateMaintenanceSchedule).mockResolvedValueOnce({
      ...schedule,
      next_due_date: '2028-02-01',
    });
    fireEvent.change(screen.getByLabelText(/next due date/i), { target: { value: '2028-02-01' } });
    fireEvent.click(screen.getByRole('button', { name: /save maintenance schedule/i }));
    expect(await screen.findByText('2028-02-01')).toBeInTheDocument();
  });

  it('recovers a concurrent create conflict by reloading the existing schedule', async () => {
    vi.mocked(getMaintenanceSchedule).mockResolvedValueOnce(empty).mockResolvedValueOnce(schedule);
    vi.mocked(createMaintenanceSchedule).mockRejectedValueOnce(
      new ApiError('conflict', 409, { detail: 'Schedule already exists' }),
    );
    render(<MaintenanceSchedulePanel assetId="a1" />);
    await screen.findByText(/no maintenance schedule yet/i);
    fireEvent.click(screen.getByRole('button', { name: /create maintenance schedule/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Schedule already exists');
    fireEvent.click(screen.getByRole('button', { name: /reload maintenance schedule/i }));
    expect(await screen.findByText('2027-04-10')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save maintenance schedule/i })).toBeEnabled();
  });
});
