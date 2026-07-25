import type { ReactElement, ReactNode } from 'react';

import { ThemeToggle } from '../shared/theme/ThemeToggle';

/** The Milestone 0 application shell: a header and one main content area. */
export function Layout({ children }: { children: ReactNode }): ReactElement {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>openQMS</h1>
        <ThemeToggle />
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
