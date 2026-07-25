import type { ReactElement } from 'react';

import { ThemeProvider } from '../shared/theme/ThemeProvider';
import { HealthStatus } from './HealthStatus';
import { Layout } from './Layout';

/**
 * Root component. Milestone 0 has exactly one screen (live API health); routing is
 * added here once a second screen exists rather than scaffolded speculatively now.
 */
export function App(): ReactElement {
  return (
    <ThemeProvider>
      <Layout>
        <HealthStatus />
      </Layout>
    </ThemeProvider>
  );
}
