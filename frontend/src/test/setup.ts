import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';

// Explicit cleanup between tests: @testing-library/react's auto-cleanup detection
// doesn't reliably trigger under this project's Vitest setup (no `globals: true`),
// so without this, renders from earlier tests in the same file remain in the DOM
// and multi-test component files intermittently see duplicate elements.
afterEach(() => {
  cleanup();
});

// jsdom does not implement the File API's object-URL methods at all (calling either
// throws "not implemented"). Real browsers do, and the document preview/download
// flows depend on them, so stub them here rather than in every test file that
// exercises those flows.
const createObjectUrlMock = vi.fn(() => 'blob:mock-object-url');
URL.createObjectURL = createObjectUrlMock;
URL.revokeObjectURL = vi.fn();

beforeEach(() => {
  // Feature tests reset their API mocks between cases with `vi.resetAllMocks()`.
  // That also clears this global mock's implementation, so restore the browser-like
  // object URL before every test.
  createObjectUrlMock.mockReturnValue('blob:mock-object-url');
});

// Deliberately NOT stubbing `HTMLAnchorElement.prototype.click` globally here: jsdom
// does not understand `<a download>`'s no-navigate semantics, so a real click()
// attempts navigation (which jsdom also doesn't implement), logging an error and
// scheduling a timer that can fire during a *later*, unrelated test. A global
// stub would hide that for every test in the suite, including ones that don't
// exercise the download flow and shouldn't need to care about it. Instead, the
// handful of tests that actually trigger the browser-download pattern (e.g.
// DocumentDetailPage.test.tsx) scope their own `vi.spyOn(HTMLAnchorElement.prototype,
// 'click')` locally.
