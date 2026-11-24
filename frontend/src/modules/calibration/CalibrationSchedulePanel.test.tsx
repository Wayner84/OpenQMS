import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import {
  createCalibrationSchedule,
  getCalibrationSchedule,
  updateCalibrationSchedule,
} from './api';
import { CalibrationSchedulePanel } from './CalibrationSchedulePanel';

vi.mock('./api');
const schedule = {
  id: 's1',
  asset_id: 'a1',
  interval_value: 12,
  interval_unit: 'months' as const,
  next_due_date: '2027-04-10',
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

describe('CalibrationSchedulePanel', () => {
  beforeEach(() => vi.mocked(getCalibrationSchedule).mockResolvedValue(schedule));
  afterEach(() => vi.resetAllMocks());

  it('shows the current due date and updates the interval and baseline', async () => {
    vi.mocked(updateCalibrationSchedule).mockResolvedValue({
      ...schedule,
      next_due_date: '2028-01-01',
    });
    render(<CalibrationSchedulePanel assetId="a1" />);
    expect(await screen.findByText('2027-04-10')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/interval value/i), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText(/interval unit/i), { target: { value: 'years' } });
    fireEvent.change(screen.getByLabelText(/next due date/i), { target: { value: '2028-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /save schedule/i }));
    await waitFor(() => {
      expect(updateCalibrationSchedule).toHaveBeenCalledWith('a1', {
        interval_value: 1,
        interval_unit: 'years',
        next_due_date: '2028-01-01',
      });
    });
  });

  it('creates a schedule only when the existing asset has none', async () => {
    vi.mocked(getCalibrationSchedule).mockRejectedValue(
      new ApiError('missing', 404, {
        detail: 'Asset a1 has no calibration schedule',
      }),
    );
    vi.mocked(createCalibrationSchedule).mockResolvedValue({ ...schedule, next_due_date: null });
    render(<CalibrationSchedulePanel assetId="a1" />);
    expect(await screen.findByText(/no calibration schedule yet/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /create schedule/i }));
    await waitFor(() => {
      expect(createCalibrationSchedule).toHaveBeenCalledWith('a1', {
        interval_value: 12,
        interval_unit: 'months',
      });
    });
  });

  it('does not offer creation when the asset itself is missing', async () => {
    vi.mocked(getCalibrationSchedule).mockRejectedValue(
      new ApiError('missing', 404, {
        detail: 'Asset not found',
      }),
    );
    render(<CalibrationSchedulePanel assetId="a1" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Asset not found');
    expect(screen.queryByRole('button', { name: /create schedule/i })).not.toBeInTheDocument();
  });

  it('settles when React StrictMode replays the effects', async () => {
    render(
      <StrictMode>
        <CalibrationSchedulePanel assetId="a1" />
      </StrictMode>,
    );
    expect(await screen.findByText('2027-04-10')).toBeInTheDocument();
    expect(screen.queryByText(/loading calibration schedule/i)).not.toBeInTheDocument();
  });

  it('does not show or submit an old schedule while a new asset loads', async () => {
    let resolveNew!: (value: typeof schedule) => void;
    vi.mocked(getCalibrationSchedule)
      .mockResolvedValueOnce(schedule)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveNew = resolve;
          }),
      );
    const { rerender } = render(<CalibrationSchedulePanel assetId="a1" />);
    await screen.findByText('2027-04-10');
    rerender(<CalibrationSchedulePanel assetId="a2" />);
    expect(screen.queryByText('2027-04-10')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /save schedule/i })).not.toBeInTheDocument();
    expect(updateCalibrationSchedule).not.toHaveBeenCalled();
    await act(async () => {
      resolveNew({ ...schedule, asset_id: 'a2', next_due_date: '2028-03-05' });
      await Promise.resolve();
    });
    expect(screen.getByText('2028-03-05')).toBeInTheDocument();
  });

  it('ignores an old asset write completing after navigation to another asset', async () => {
    let resolveWrite!: (value: typeof schedule) => void;
    vi.mocked(updateCalibrationSchedule).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveWrite = resolve;
        }),
    );
    vi.mocked(getCalibrationSchedule)
      .mockResolvedValueOnce(schedule)
      .mockResolvedValueOnce({
        ...schedule,
        asset_id: 'a2',
        next_due_date: '2028-03-05',
      });
    const { rerender } = render(<CalibrationSchedulePanel assetId="a1" />);
    await screen.findByText('2027-04-10');
    fireEvent.click(screen.getByRole('button', { name: /save schedule/i }));
    await waitFor(() => {
      expect(updateCalibrationSchedule).toHaveBeenCalledWith('a1', expect.anything());
    });
    rerender(<CalibrationSchedulePanel assetId="a2" />);
    expect(await screen.findByText('2028-03-05')).toBeInTheDocument();
    await act(async () => {
      resolveWrite(schedule);
      await Promise.resolve();
    });
    expect(screen.getByText('2028-03-05')).toBeInTheDocument();
    expect(screen.queryByText('2027-04-10')).not.toBeInTheDocument();
  });

  it('rejects clearing an existing due date rather than pretending to persist it', async () => {
    vi.mocked(updateCalibrationSchedule).mockResolvedValue(schedule);
    render(<CalibrationSchedulePanel assetId="a1" />);
    await screen.findByText('2027-04-10');
    fireEvent.change(screen.getByLabelText(/next due date/i), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /save schedule/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/clearing.*not supported/i);
    expect(updateCalibrationSchedule).not.toHaveBeenCalled();
  });

  it('classifies overdue, today and upcoming against the UTC calendar date', async () => {
    const day = new Date().toISOString().slice(0, 10);
    const yesterday = new Date(Date.parse(`${day}T00:00:00Z`) - 86400000)
      .toISOString()
      .slice(0, 10);
    const tomorrow = new Date(Date.parse(`${day}T00:00:00Z`) + 86400000).toISOString().slice(0, 10);
    for (const [date, label] of [
      [yesterday, 'Overdue'],
      [day, 'Due today'],
      [tomorrow, 'Upcoming'],
    ] as const) {
      vi.mocked(getCalibrationSchedule).mockResolvedValueOnce({ ...schedule, next_due_date: date });
      const { unmount } = render(<CalibrationSchedulePanel assetId="a1" />);
      expect(await screen.findByText(new RegExp(label))).toBeInTheDocument();
      unmount();
    }
  });
});
