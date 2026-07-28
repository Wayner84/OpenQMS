import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';

import { getErrorDetail } from '../../shared/api/client';
import { compareVersions } from './api';
import type { DocumentVersion, VersionComparisonResponse } from './types';

/**
 * An in-page panel (per the Milestone 2 plan, "VersionComparePage.tsx (or an
 * in-page panel)") to select two versions of a document and view a practical
 * comparison: version-level metadata always, plus a unified text diff when both
 * versions are text-based, or just whether the binary content changed otherwise.
 */
export function VersionComparePanel({
  documentId,
  versions,
}: {
  documentId: string;
  versions: DocumentVersion[];
}): ReactElement {
  const [versionAId, setVersionAId] = useState('');
  const [versionBId, setVersionBId] = useState('');
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [result, setResult] = useState<VersionComparisonResponse | null>(null);
  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);

  useEffect(() => {
    // Set (not just read) on every (re-)mount, not only cleared on unmount: React 18
    // StrictMode double-invokes this effect in development (mount, cleanup, mount
    // again) to surface missing-cleanup bugs. See CodingStandards.md#frontend-react-typescript.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // `documentId` is a prop, not driven by this component's own state -- the
    // parent (DocumentDetailPage) can reuse this same component instance across a
    // navigation to a different document (React only remounts on a `key` change,
    // and there isn't one here), so a change to `documentId` must reset the
    // selected versions and any comparison result already shown, and invalidate
    // any in-flight comparison request -- all of which are otherwise scoped to
    // the *previous* document's version ids.
    requestIdRef.current += 1;
    setVersionAId('');
    setVersionBId('');
    setResult(null);
    setCompareError(null);
    setComparing(false);
  }, [documentId]);

  const handleCompare = (): void => {
    if (!versionAId || !versionBId) {
      return;
    }
    // A later comparison (a different version pair selected and compared again
    // before the first request lands) must win even if its response arrives
    // first -- an out-of-order response from an *earlier* request must never
    // overwrite a result a *later* request already set.
    const requestId = ++requestIdRef.current;
    setCompareError(null);
    setComparing(true);
    void (async () => {
      try {
        const comparison = await compareVersions(documentId, versionAId, versionBId);
        if (mountedRef.current && requestIdRef.current === requestId) {
          setResult(comparison);
        }
      } catch (err) {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setCompareError(
            getErrorDetail(err) ?? 'Could not compare these versions. Please try again.',
          );
          setResult(null);
        }
      } finally {
        if (mountedRef.current && requestIdRef.current === requestId) {
          setComparing(false);
        }
      }
    })();
  };

  if (versions.length < 2) {
    return (
      <section>
        <h3>Compare versions</h3>
        <p>At least two versions are needed to compare.</p>
      </section>
    );
  }

  return (
    <section>
      <h3>Compare versions</h3>
      {compareError && (
        <p role="alert" className="auth-form__error">
          {compareError}
        </p>
      )}
      <div className="form-field">
        <label htmlFor="compare-version-a">Version A</label>
        <select
          id="compare-version-a"
          value={versionAId}
          onChange={(event) => {
            setVersionAId(event.target.value);
          }}
        >
          <option value="">Select a version…</option>
          {versions.map((version) => (
            <option key={version.id} value={version.id}>
              v{version.version_number} — {version.original_filename}
            </option>
          ))}
        </select>
      </div>
      <div className="form-field">
        <label htmlFor="compare-version-b">Version B</label>
        <select
          id="compare-version-b"
          value={versionBId}
          onChange={(event) => {
            setVersionBId(event.target.value);
          }}
        >
          <option value="">Select a version…</option>
          {versions.map((version) => (
            <option key={version.id} value={version.id}>
              v{version.version_number} — {version.original_filename}
            </option>
          ))}
        </select>
      </div>
      <button
        type="button"
        className="button button--primary"
        disabled={!versionAId || !versionBId || comparing}
        onClick={handleCompare}
      >
        {comparing ? 'Comparing…' : 'Compare'}
      </button>

      {result && (
        <div>
          <h4>Comparison result</h4>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col"></th>
                  <th scope="col">Version A</th>
                  <th scope="col">Version B</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Version</th>
                  <td>v{result.version_a.version_number}</td>
                  <td>v{result.version_b.version_number}</td>
                </tr>
                <tr>
                  <th scope="row">Status</th>
                  <td>{result.version_a.status}</td>
                  <td>{result.version_b.status}</td>
                </tr>
                <tr>
                  <th scope="row">Size (bytes)</th>
                  <td>{result.version_a.size_bytes}</td>
                  <td>{result.version_b.size_bytes}</td>
                </tr>
                <tr>
                  <th scope="row">Change summary</th>
                  <td>{result.version_a.change_summary}</td>
                  <td>{result.version_b.change_summary}</td>
                </tr>
                <tr>
                  <th scope="row">Uploaded</th>
                  <td>{result.version_a.created_at}</td>
                  <td>{result.version_b.created_at}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {result.text_diff ? (
            result.text_diff.length === 0 ? (
              <p>The content is identical.</p>
            ) : (
              <pre>
                <code>{result.text_diff.join('')}</code>
              </pre>
            )
          ) : (
            <p>
              {result.checksum_changed
                ? 'The binary content changed between these versions.'
                : 'The binary content is unchanged between these versions.'}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
