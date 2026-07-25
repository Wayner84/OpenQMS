import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';

import { getHealth, getReadiness } from '../shared/api/health';
import type { LivenessResponse, ReadinessResponse } from '../shared/api/health';

type HealthState =
  | { status: 'loading' }
  | { status: 'success'; liveness: LivenessResponse; readiness: ReadinessResponse }
  | { status: 'error'; message: string };

/** The one Milestone 0 screen: calls the health/readiness endpoints and shows live status. */
export function HealthStatus(): ReactElement {
  const [state, setState] = useState<HealthState>({ status: 'loading' });

  useEffect(() => {
    const controller = new AbortController();

    void (async () => {
      try {
        const [liveness, readiness] = await Promise.all([getHealth(), getReadiness()]);
        if (!controller.signal.aborted) {
          setState({ status: 'success', liveness, readiness });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Unknown error',
          });
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, []);

  if (state.status === 'loading') {
    return (
      <p role="status" className="health-status">
        Checking API health…
      </p>
    );
  }

  if (state.status === 'error') {
    return (
      <p role="alert" className="health-status health-status--error">
        API is unreachable: {state.message}
      </p>
    );
  }

  return (
    <div role="status" className="health-status">
      <p>API is healthy: {state.liveness.status}</p>
      <p>
        Readiness: {state.readiness.status} (database: {state.readiness.database})
      </p>
    </div>
  );
}
