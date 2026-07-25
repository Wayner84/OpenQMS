import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { getHealth, getReadiness } from '../shared/api/health';
import { HealthStatus } from './HealthStatus';

vi.mock('../shared/api/health');

const mockedGetHealth = vi.mocked(getHealth);
const mockedGetReadiness = vi.mocked(getReadiness);

describe('HealthStatus', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state before the health checks resolve', () => {
    mockedGetHealth.mockReturnValue(new Promise(() => {}));
    mockedGetReadiness.mockReturnValue(new Promise(() => {}));

    render(<HealthStatus />);

    expect(screen.getByRole('status')).toHaveTextContent(/checking/i);
  });

  it('shows a healthy summary once liveness and readiness both succeed', async () => {
    mockedGetHealth.mockResolvedValue({ status: 'ok' });
    mockedGetReadiness.mockResolvedValue({ status: 'ready', database: 'ok' });

    render(<HealthStatus />);

    await waitFor(() => {
      expect(screen.getByText(/api is healthy/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/database: ok/i)).toBeInTheDocument();
  });

  it('shows an error state when a health check request fails', async () => {
    mockedGetHealth.mockRejectedValue(new Error('network down'));
    mockedGetReadiness.mockResolvedValue({ status: 'ready', database: 'ok' });

    render(<HealthStatus />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/unreachable/i);
    });
  });
});
