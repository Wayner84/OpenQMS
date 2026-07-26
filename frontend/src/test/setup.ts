import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Explicit cleanup between tests: @testing-library/react's auto-cleanup detection
// doesn't reliably trigger under this project's Vitest setup (no `globals: true`),
// so without this, renders from earlier tests in the same file remain in the DOM
// and multi-test component files intermittently see duplicate elements.
afterEach(() => {
  cleanup();
});
