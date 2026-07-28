import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { compareVersions } from './api';
import type { DocumentVersion } from './types';
import { VersionComparePanel } from './VersionComparePanel';

vi.mock('./api');

const mockedCompareVersions = vi.mocked(compareVersions);

/** A promise plus its resolvers, for tests that need precise control over when a
 * mocked comparison settles -- used to prove an out-of-order (slower, earlier)
 * response can't overwrite a newer selection's result. */
function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
} {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

const versionA: DocumentVersion = {
  id: 'v1',
  document_id: 'd1',
  version_number: 1,
  original_filename: 'notes.txt',
  content_type: 'text/plain',
  size_bytes: 10,
  checksum_sha256: 'a',
  change_summary: 'Initial',
  status: 'approved',
  created_by_id: 'u1',
  created_at: '2026-07-26T00:00:00Z',
};

const versionB: DocumentVersion = {
  ...versionA,
  id: 'v2',
  version_number: 2,
  checksum_sha256: 'b',
  change_summary: 'Revised',
};

describe('VersionComparePanel', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a message instead of the form when fewer than two versions exist', () => {
    render(<VersionComparePanel documentId="d1" versions={[versionA]} />);

    expect(screen.getByText(/at least two versions are needed/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /compare/i })).not.toBeInTheDocument();
  });

  it('compares two selected versions and shows the text diff', async () => {
    mockedCompareVersions.mockResolvedValue({
      version_a: versionA,
      version_b: versionB,
      checksum_changed: true,
      text_diff: ['-old line\n', '+new line\n'],
    });

    render(<VersionComparePanel documentId="d1" versions={[versionA, versionB]} />);

    fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
    fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
    fireEvent.click(screen.getByRole('button', { name: /^compare$/i }));

    await waitFor(() => {
      expect(mockedCompareVersions).toHaveBeenCalledWith('d1', 'v1', 'v2');
    });
    expect(await screen.findByText(/new line/)).toBeInTheDocument();
  });

  it('shows a binary-changed message when there is no text diff', async () => {
    mockedCompareVersions.mockResolvedValue({
      version_a: { ...versionA, content_type: 'application/pdf' },
      version_b: { ...versionB, content_type: 'application/pdf' },
      checksum_changed: true,
      text_diff: null,
    });

    render(<VersionComparePanel documentId="d1" versions={[versionA, versionB]} />);

    fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
    fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
    fireEvent.click(screen.getByRole('button', { name: /^compare$/i }));

    expect(await screen.findByText(/binary content changed/i)).toBeInTheDocument();
  });

  it('shows an unchanged message when the content is identical', async () => {
    mockedCompareVersions.mockResolvedValue({
      version_a: versionA,
      version_b: versionB,
      checksum_changed: false,
      text_diff: [],
    });

    render(<VersionComparePanel documentId="d1" versions={[versionA, versionB]} />);

    fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
    fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
    fireEvent.click(screen.getByRole('button', { name: /^compare$/i }));

    expect(await screen.findByText(/content is identical/i)).toBeInTheDocument();
  });

  it('shows an error message when the comparison fails', async () => {
    mockedCompareVersions.mockRejectedValue(new Error('network error'));

    render(<VersionComparePanel documentId="d1" versions={[versionA, versionB]} />);

    fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
    fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
    fireEvent.click(screen.getByRole('button', { name: /^compare$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not compare/i);
  });

  it('renders correctly under React StrictMode (dev-mode double-invokes effects on mount)', () => {
    render(
      <StrictMode>
        <VersionComparePanel documentId="d1" versions={[versionA, versionB]} />
      </StrictMode>,
    );

    expect(screen.getByRole('button', { name: /^compare$/i })).toBeInTheDocument();
  });

  it('wraps the comparison result table for responsive/narrow-screen scrolling', async () => {
    mockedCompareVersions.mockResolvedValue({
      version_a: versionA,
      version_b: versionB,
      checksum_changed: true,
      text_diff: null,
    });

    render(<VersionComparePanel documentId="d1" versions={[versionA, versionB]} />);

    fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
    fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
    fireEvent.click(screen.getByRole('button', { name: /^compare$/i }));

    const table = await screen.findByRole('table');
    expect(table.closest('.data-table-wrapper')).not.toBeNull();
  });

  it('disables the compare button while a comparison is in flight, so a second selection cannot start an overlapping request through the UI', async () => {
    const pending = deferred<{
      version_a: DocumentVersion;
      version_b: DocumentVersion;
      checksum_changed: boolean;
      text_diff: string[] | null;
    }>();
    mockedCompareVersions.mockReturnValue(pending.promise);

    render(<VersionComparePanel documentId="d1" versions={[versionA, versionB]} />);

    fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
    fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
    const compareButton = screen.getByRole('button', { name: /^compare$/i });
    fireEvent.click(compareButton);

    await waitFor(() => {
      expect(compareButton).toBeDisabled();
    });

    pending.resolve({
      version_a: versionA,
      version_b: versionB,
      checksum_changed: false,
      text_diff: [],
    });
    expect(await screen.findByText(/content is identical/i)).toBeInTheDocument();
  });

  describe('documentId changes (component instance reused by the parent for a different document)', () => {
    it('resets the selected versions and any comparison result when documentId changes', async () => {
      mockedCompareVersions.mockResolvedValue({
        version_a: versionA,
        version_b: versionB,
        checksum_changed: true,
        text_diff: ['-old line\n', '+new line\n'],
      });

      const { rerender } = render(
        <VersionComparePanel documentId="d1" versions={[versionA, versionB]} />,
      );
      fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
      fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
      fireEvent.click(screen.getByRole('button', { name: /^compare$/i }));
      expect(await screen.findByText(/new line/)).toBeInTheDocument();

      rerender(<VersionComparePanel documentId="d2" versions={[versionA, versionB]} />);

      expect(screen.queryByText(/comparison result/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText(/version a/i)).toHaveValue('');
      expect(screen.getByLabelText(/version b/i)).toHaveValue('');
    });

    it('does not let a stale comparison response from a previous documentId apply after it changes', async () => {
      const pending = deferred<{
        version_a: DocumentVersion;
        version_b: DocumentVersion;
        checksum_changed: boolean;
        text_diff: string[] | null;
      }>();
      mockedCompareVersions.mockReturnValue(pending.promise);

      const { rerender } = render(
        <VersionComparePanel documentId="d1" versions={[versionA, versionB]} />,
      );
      fireEvent.change(screen.getByLabelText(/version a/i), { target: { value: 'v1' } });
      fireEvent.change(screen.getByLabelText(/version b/i), { target: { value: 'v2' } });
      fireEvent.click(screen.getByRole('button', { name: /^compare$/i }));

      rerender(<VersionComparePanel documentId="d2" versions={[versionA, versionB]} />);

      pending.resolve({
        version_a: versionA,
        version_b: versionB,
        checksum_changed: false,
        text_diff: [],
      });
      await Promise.resolve();
      await Promise.resolve();

      expect(screen.queryByText(/comparison result/i)).not.toBeInTheDocument();
    });
  });
});
