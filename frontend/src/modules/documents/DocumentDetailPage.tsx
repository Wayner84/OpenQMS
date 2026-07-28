import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, FormEvent, ReactElement } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { useAuth } from '../auth/AuthContext';
import { listPeople } from '../people/api';
import type { Person } from '../people/types';
import {
  acknowledgeVersion,
  approveVersion,
  deleteDocument,
  downloadDocumentVersion,
  getDocument,
  listCategories,
  listDocumentVersions,
  listTags,
  listVersionAcknowledgements,
  previewDocumentVersion,
  rejectVersion,
  retireDocument,
  submitVersionForApproval,
  updateDocument,
  uploadDocumentVersion,
} from './api';
import { VersionComparePanel } from './VersionComparePanel';
import type {
  Category,
  DocumentAcknowledgement,
  DocumentRecord,
  DocumentVersion,
  Tag,
} from './types';
import { PREVIEWABLE_CONTENT_TYPES } from './types';

/** Real browsers need time to start consuming a `blob:` URL after a
 * programmatic download click before it's safe to revoke -- revoking
 * synchronously can abort the download in some browsers. There is no reliable
 * "download started" event, so a generous fixed delay is the practical choice. */
const DOWNLOAD_URL_REVOKE_DELAY_MS = 30_000;

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  link.download = filename;
  window.document.body.appendChild(link);
  link.click();
  window.document.body.removeChild(link);
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, DOWNLOAD_URL_REVOKE_DELAY_MS);
}

function personDisplayName(person: Person): string {
  return `${person.first_name} ${person.last_name}`;
}

interface MetadataForm {
  title: string;
  categoryId: string;
  ownerId: string;
  tagIds: string[];
}

function toMetadataForm(document: DocumentRecord): MetadataForm {
  return {
    title: document.title,
    categoryId: document.category_id ?? '',
    ownerId: document.owner_id ?? '',
    tagIds: document.tags.map((tag) => tag.id),
  };
}

/**
 * A single document: metadata (with an edit form), version history, upload-new-
 * version form, workflow actions (submit/approve/reject/retire/delete — shown per
 * the current user's role and the version's state, always re-enforced server-side),
 * acknowledgement, preview, and download. Version comparison is a separate in-page
 * panel ({@link VersionComparePanel}).
 */
export function DocumentDetailPage(): ReactElement {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const navigate = useNavigate();

  const [documentRecord, setDocumentRecord] = useState<DocumentRecord | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingVersionIds, setPendingVersionIds] = useState<ReadonlySet<string>>(new Set());

  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [editingMetadata, setEditingMetadata] = useState(false);
  const [metadataForm, setMetadataForm] = useState<MetadataForm>({
    title: '',
    categoryId: '',
    ownerId: '',
    tagIds: [],
  });
  const [savingMetadata, setSavingMetadata] = useState(false);

  const [retiring, setRetiring] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [changeSummary, setChangeSummary] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});

  const [expandedAckVersionId, setExpandedAckVersionId] = useState<string | null>(null);
  const [acknowledgements, setAcknowledgements] = useState<DocumentAcknowledgement[]>([]);
  const [acknowledgementsLoading, setAcknowledgementsLoading] = useState(false);

  const [previewVersionId, setPreviewVersionId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewContentType, setPreviewContentType] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const currentDocumentIdRef = useRef(id);
  const previewUrlRef = useRef<string | null>(null);
  const loadRequestIdRef = useRef(0);
  const ackRequestIdRef = useRef(0);
  const previewRequestIdRef = useRef(0);
  const optionsRequestIdRef = useRef(0);
  currentDocumentIdRef.current = id;

  useEffect(() => {
    // Set (not just read) on every (re-)mount, not only cleared on unmount: React 18
    // StrictMode double-invokes this effect in development (mount, cleanup, mount
    // again) to surface missing-cleanup bugs. Without resetting to `true` here, the
    // cleanup from that simulated first mount leaves this permanently `false`, so
    // every subsequent `if (mountedRef.current) setState(...)` below silently no-ops
    // — including the ones that turn off the initial loading state.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(
    () => () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    if (!id) {
      return;
    }
    const requestId = ++optionsRequestIdRef.current;
    const requestDocumentId = id;
    setOptionsError(null);
    void Promise.all([
      fetchAllPages<Category>((params) => listCategories(params)),
      fetchAllPages<Tag>((params) => listTags(params)),
      fetchAllPages<Person>((params) => listPeople(params)),
    ])
      .then(([categoryItems, tagItems, peopleItems]) => {
        if (
          mountedRef.current &&
          currentDocumentIdRef.current === requestDocumentId &&
          optionsRequestIdRef.current === requestId
        ) {
          setCategories(categoryItems);
          setTags(tagItems);
          setPeople(peopleItems);
        }
      })
      .catch(() => {
        if (
          mountedRef.current &&
          currentDocumentIdRef.current === requestDocumentId &&
          optionsRequestIdRef.current === requestId
        ) {
          setOptionsError('Could not load categories/tags/owners for editing. Please try again.');
        }
      });
  }, [id]);

  const categoryNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const category of categories) {
      map.set(category.id, category.name);
    }
    return map;
  }, [categories]);

  const ownerNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const person of people) {
      map.set(person.id, personDisplayName(person));
    }
    return map;
  }, [people]);

  const loadAll = useCallback(async () => {
    if (!id || currentDocumentIdRef.current !== id) {
      return;
    }
    // A later call to `loadAll` (a route-id change to a different document, or a
    // refresh triggered by an action while a previous load was still in flight)
    // must win even if its response arrives first -- an out-of-order response from
    // an *earlier* request must never overwrite state a *later* request already
    // set. Guarding on a monotonically increasing request id (not just
    // `mountedRef`, which only covers unmount) makes that ordering explicit rather
    // than assuming responses arrive in request order.
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    setLoadError(null);
    try {
      const [documentResult, versionItems] = await Promise.all([
        getDocument(id),
        fetchAllPages<DocumentVersion>((params) => listDocumentVersions(id, params)),
      ]);
      if (
        mountedRef.current &&
        currentDocumentIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setDocumentRecord(documentResult);
        setVersions(versionItems);
      }
    } catch {
      if (
        mountedRef.current &&
        currentDocumentIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoadError('Could not load this document. Please try again.');
      }
    } finally {
      if (
        mountedRef.current &&
        currentDocumentIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoading(false);
      }
    }
  }, [id]);

  useEffect(() => {
    // This component instance can be reused across navigations to a *different*
    // document (e.g. clicking another document's link from a page this one links
    // back to) -- React only remounts on a `key` change, and the route only
    // changes `:id`, not the element's identity. Every piece of state scoped to
    // the *previous* document must therefore be reset here, and any of its
    // in-flight ack/preview requests invalidated, or d1's actions/errors/expanded
    // panels/preview would still be showing (or, worse, a late d1 response could
    // still land) after the user has navigated to d2.
    ackRequestIdRef.current += 1;
    previewRequestIdRef.current += 1;
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setDocumentRecord(null);
    setVersions([]);
    setLoadError(null);
    setActionError(null);
    setPendingVersionIds(new Set());
    setEditingMetadata(false);
    setMetadataForm({ title: '', categoryId: '', ownerId: '', tagIds: [] });
    setSavingMetadata(false);
    setRetiring(false);
    setDeleting(false);
    setUploadFile(null);
    setChangeSummary('');
    setUploading(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setReviewComments({});
    setExpandedAckVersionId(null);
    setAcknowledgements([]);
    setAcknowledgementsLoading(false);
    setPreviewVersionId(null);
    setPreviewUrl(null);
    setPreviewContentType(null);
    setPreviewLoading(false);
    setPreviewError(null);
  }, [id]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const withPending = (versionId: string, action: () => Promise<void>): void => {
    const actionDocumentId = id;
    setActionError(null);
    setPendingVersionIds((current) => new Set(current).add(versionId));
    void (async () => {
      try {
        await action();
        if (currentDocumentIdRef.current === actionDocumentId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setActionError(
            getErrorDetail(err) ?? 'That action could not be completed. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setPendingVersionIds((current) => {
            const next = new Set(current);
            next.delete(versionId);
            return next;
          });
        }
      }
    })();
  };

  const handleUploadSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id || !uploadFile) {
      return;
    }
    setActionError(null);
    setUploading(true);
    const actionDocumentId = id;
    void (async () => {
      try {
        await uploadDocumentVersion(id, uploadFile, changeSummary || undefined);
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setUploadFile(null);
          setChangeSummary('');
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setActionError(getErrorDetail(err) ?? 'Could not upload this version. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setUploading(false);
        }
      }
    })();
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setUploadFile(event.target.files?.[0] ?? null);
  };

  const handleSubmitForApproval = (version: DocumentVersion): void => {
    if (!id) {
      return;
    }
    withPending(version.id, async () => {
      await submitVersionForApproval(id, version.id);
    });
  };

  const handleApprove = (version: DocumentVersion): void => {
    if (!id) {
      return;
    }
    const comments = reviewComments[version.id];
    withPending(version.id, async () => {
      await approveVersion(id, version.id, comments);
    });
  };

  const handleReject = (version: DocumentVersion): void => {
    if (!id) {
      return;
    }
    const comments = reviewComments[version.id];
    if (!comments || !comments.trim()) {
      setActionError('A comment explaining the rejection is required.');
      return;
    }
    withPending(version.id, async () => {
      await rejectVersion(id, version.id, comments);
    });
  };

  const handleRetire = (): void => {
    if (!id || !documentRecord) {
      return;
    }
    if (!window.confirm('Retire this document? It will be marked obsolete for every user.')) {
      return;
    }
    setActionError(null);
    setRetiring(true);
    const actionDocumentId = id;
    void (async () => {
      try {
        await retireDocument(id);
        if (currentDocumentIdRef.current === actionDocumentId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not retire this document. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setRetiring(false);
        }
      }
    })();
  };

  const handleDeleteDocument = (): void => {
    if (!id) {
      return;
    }
    if (
      !window.confirm(
        'Delete this document? It will be removed from lists and searches for every user.',
      )
    ) {
      return;
    }
    setActionError(null);
    setDeleting(true);
    const actionDocumentId = id;
    void (async () => {
      try {
        await deleteDocument(id);
        if (currentDocumentIdRef.current === actionDocumentId) {
          void navigate('/documents');
        }
      } catch (err) {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not delete this document. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setDeleting(false);
        }
      }
    })();
  };

  const startEditMetadata = (): void => {
    if (!documentRecord) {
      return;
    }
    setActionError(null);
    setMetadataForm(toMetadataForm(documentRecord));
    setEditingMetadata(true);
  };

  const cancelEditMetadata = (): void => {
    setEditingMetadata(false);
  };

  const toggleMetadataTag = (tagId: string): void => {
    setMetadataForm((current) => ({
      ...current,
      tagIds: current.tagIds.includes(tagId)
        ? current.tagIds.filter((existing) => existing !== tagId)
        : [...current.tagIds, tagId],
    }));
  };

  const handleMetadataSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id) {
      return;
    }
    setActionError(null);
    setSavingMetadata(true);
    const actionDocumentId = id;
    void (async () => {
      try {
        await updateDocument(id, {
          title: metadataForm.title,
          category_id: metadataForm.categoryId || undefined,
          owner_id: metadataForm.ownerId || undefined,
          tag_ids: metadataForm.tagIds,
        });
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setEditingMetadata(false);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setActionError(getErrorDetail(err) ?? 'Could not save these changes. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentDocumentIdRef.current === actionDocumentId) {
          setSavingMetadata(false);
        }
      }
    })();
  };

  const refreshAcknowledgements = (versionId: string): void => {
    if (!id) {
      return;
    }
    const requestId = ++ackRequestIdRef.current;
    const requestDocumentId = id;
    setAcknowledgementsLoading(true);
    void (async () => {
      try {
        const items = await fetchAllPages<DocumentAcknowledgement>((params) =>
          listVersionAcknowledgements(id, versionId, params),
        );
        if (
          mountedRef.current &&
          currentDocumentIdRef.current === requestDocumentId &&
          ackRequestIdRef.current === requestId
        ) {
          setAcknowledgements(items);
        }
      } catch {
        if (
          mountedRef.current &&
          currentDocumentIdRef.current === requestDocumentId &&
          ackRequestIdRef.current === requestId
        ) {
          setActionError('Could not load acknowledgements. Please try again.');
        }
      } finally {
        if (
          mountedRef.current &&
          currentDocumentIdRef.current === requestDocumentId &&
          ackRequestIdRef.current === requestId
        ) {
          setAcknowledgementsLoading(false);
        }
      }
    })();
  };

  const handleAcknowledge = (version: DocumentVersion): void => {
    if (!id) {
      return;
    }
    withPending(version.id, async () => {
      await acknowledgeVersion(id, version.id);
      if (expandedAckVersionId === version.id) {
        refreshAcknowledgements(version.id);
      }
    });
  };

  const toggleAcknowledgements = (version: DocumentVersion): void => {
    if (!id) {
      return;
    }
    if (expandedAckVersionId === version.id) {
      // Invalidate any in-flight request for the version being collapsed so a
      // late response can't reopen/repopulate it after the user has moved on.
      ackRequestIdRef.current += 1;
      setExpandedAckVersionId(null);
      setAcknowledgements([]);
      return;
    }
    setExpandedAckVersionId(version.id);
    refreshAcknowledgements(version.id);
  };

  const togglePreview = (version: DocumentVersion): void => {
    if (!id) {
      return;
    }
    if (previewVersionId === version.id) {
      // Invalidate any in-flight request for the version being hidden -- without
      // this, a response that arrives after the user has already closed the
      // preview would still apply, leaking its object URL (never revoked) and
      // potentially reopening a preview the user just dismissed.
      previewRequestIdRef.current += 1;
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
      }
      setPreviewVersionId(null);
      setPreviewUrl(null);
      setPreviewContentType(null);
      return;
    }
    setPreviewError(null);
    setPreviewLoading(true);
    setPreviewVersionId(version.id);
    const requestId = ++previewRequestIdRef.current;
    void (async () => {
      try {
        const blob = await previewDocumentVersion(id, version.id);
        if (!PREVIEWABLE_CONTENT_TYPES.has(blob.type)) {
          if (mountedRef.current && previewRequestIdRef.current === requestId) {
            setPreviewError(
              'Unexpected content type returned for this preview; use download instead.',
            );
          }
          return;
        }
        const url = URL.createObjectURL(blob);
        if (mountedRef.current && previewRequestIdRef.current === requestId) {
          if (previewUrlRef.current) {
            URL.revokeObjectURL(previewUrlRef.current);
          }
          previewUrlRef.current = url;
          setPreviewUrl(url);
          setPreviewContentType(blob.type);
        } else {
          URL.revokeObjectURL(url);
        }
      } catch (err) {
        if (mountedRef.current && previewRequestIdRef.current === requestId) {
          setPreviewError(getErrorDetail(err) ?? 'Could not load a preview for this version.');
        }
      } finally {
        if (mountedRef.current && previewRequestIdRef.current === requestId) {
          setPreviewLoading(false);
        }
      }
    })();
  };

  const handleDownload = (version: DocumentVersion): void => {
    if (!id) {
      return;
    }
    setActionError(null);
    const requestDocumentId = id;
    void (async () => {
      try {
        const blob = await downloadDocumentVersion(id, version.id);
        if (mountedRef.current && currentDocumentIdRef.current === requestDocumentId) {
          triggerBrowserDownload(blob, version.original_filename);
        }
      } catch (err) {
        if (mountedRef.current && currentDocumentIdRef.current === requestDocumentId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not download this version. Please try again.',
          );
        }
      }
    })();
  };

  if (!id) {
    return <p role="alert">No document specified.</p>;
  }

  return (
    <section>
      {loading && (
        <p role="status" className="auth-loading">
          Loading…
        </p>
      )}
      {loadError && (
        <p role="alert" className="auth-form__error">
          {loadError}
        </p>
      )}

      {!loading && !loadError && documentRecord && (
        <>
          <h2>
            {documentRecord.number} — {documentRecord.title}
          </h2>
          <p>
            Status: {documentRecord.status}
            {' · '}
            Category:{' '}
            {documentRecord.category_id
              ? (categoryNameById.get(documentRecord.category_id) ?? documentRecord.category_id)
              : 'None'}
            {' · '}
            Owner:{' '}
            {documentRecord.owner_id
              ? (ownerNameById.get(documentRecord.owner_id) ?? documentRecord.owner_id)
              : 'Unassigned'}
            {documentRecord.tags.length > 0 && (
              <> · Tags: {documentRecord.tags.map((tag) => tag.name).join(', ')}</>
            )}
          </p>
          {actionError && (
            <p role="alert" className="auth-form__error">
              {actionError}
            </p>
          )}
          {optionsError && (
            <p role="alert" className="auth-form__error">
              {optionsError}
            </p>
          )}
          <button
            type="button"
            className="button"
            onClick={editingMetadata ? cancelEditMetadata : startEditMetadata}
          >
            {editingMetadata ? 'Cancel editing' : 'Edit details'}
          </button>{' '}
          {isAdmin && documentRecord.status !== 'obsolete' && (
            <button type="button" className="button" disabled={retiring} onClick={handleRetire}>
              {retiring ? 'Retiring…' : 'Retire document'}
            </button>
          )}{' '}
          {isAdmin && (
            <button
              type="button"
              className="button"
              disabled={deleting}
              onClick={handleDeleteDocument}
            >
              {deleting ? 'Deleting…' : 'Delete document'}
            </button>
          )}
          {editingMetadata && (
            <form
              className="auth-form"
              onSubmit={handleMetadataSubmit}
              aria-label="Edit document details"
            >
              <div className="form-field">
                <label htmlFor="metadata-title">Title</label>
                <input
                  id="metadata-title"
                  required
                  value={metadataForm.title}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, title: event.target.value }));
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="metadata-category">Category</label>
                <select
                  id="metadata-category"
                  value={metadataForm.categoryId}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, categoryId: event.target.value }));
                  }}
                >
                  <option value="">No category</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="metadata-owner">Owner</label>
                <select
                  id="metadata-owner"
                  value={metadataForm.ownerId}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, ownerId: event.target.value }));
                  }}
                >
                  <option value="">Unassigned</option>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {personDisplayName(person)}
                    </option>
                  ))}
                </select>
              </div>
              {tags.length > 0 && (
                <fieldset className="form-field">
                  <legend>Tags</legend>
                  {tags.map((tag) => (
                    <label key={tag.id} htmlFor={`metadata-tag-${tag.id}`}>
                      <input
                        id={`metadata-tag-${tag.id}`}
                        type="checkbox"
                        checked={metadataForm.tagIds.includes(tag.id)}
                        onChange={() => {
                          toggleMetadataTag(tag.id);
                        }}
                      />{' '}
                      {tag.name}
                    </label>
                  ))}
                </fieldset>
              )}
              <button type="submit" className="button button--primary" disabled={savingMetadata}>
                {savingMetadata ? 'Saving…' : 'Save changes'}
              </button>{' '}
              <button type="button" className="button" onClick={cancelEditMetadata}>
                Cancel
              </button>
            </form>
          )}
          <h3>Upload a new version</h3>
          <form
            className="auth-form"
            onSubmit={handleUploadSubmit}
            aria-label="Upload a new version"
          >
            <div className="form-field">
              <label htmlFor="version-file">File</label>
              {/* No native `required`: the submit button is already disabled until a
                  file is chosen (see `disabled={uploading || !uploadFile}` below), so
                  this would be redundant enforcement, and jsdom's constraint
                  validation for `type="file"` does not recognise a file attached via
                  the standard RTL `fireEvent.change` pattern, which would silently
                  block submission in tests without blocking anything in a real
                  browser (where a genuine file-picker selection is recognised). */}
              <input id="version-file" type="file" ref={fileInputRef} onChange={handleFileChange} />
            </div>
            <div className="form-field">
              <label htmlFor="version-change-summary">Change summary</label>
              <input
                id="version-change-summary"
                value={changeSummary}
                onChange={(event) => {
                  setChangeSummary(event.target.value);
                }}
              />
            </div>
            <button
              type="submit"
              className="button button--primary"
              disabled={uploading || !uploadFile}
            >
              {uploading ? 'Uploading…' : 'Upload version'}
            </button>
          </form>
          <h3>Version history</h3>
          {versions.length === 0 ? (
            <p>No versions uploaded yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Version</th>
                    <th scope="col">File</th>
                    <th scope="col">Status</th>
                    <th scope="col">Uploaded</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((version) => {
                    const isPending = pendingVersionIds.has(version.id);
                    const isPreviewable = PREVIEWABLE_CONTENT_TYPES.has(version.content_type);
                    const isImagePreview = previewContentType?.startsWith('image/') ?? false;
                    return (
                      <tr key={version.id}>
                        <td>v{version.version_number}</td>
                        <td>{version.original_filename}</td>
                        <td>{version.status}</td>
                        <td>{version.created_at}</td>
                        <td>
                          <button
                            type="button"
                            className="button"
                            disabled={isPending}
                            onClick={() => {
                              handleDownload(version);
                            }}
                          >
                            Download {version.original_filename}
                          </button>{' '}
                          {isPreviewable ? (
                            <button
                              type="button"
                              className="button"
                              disabled={isPending}
                              onClick={() => {
                                togglePreview(version);
                              }}
                            >
                              {previewVersionId === version.id ? 'Hide preview' : 'Preview'}
                            </button>
                          ) : (
                            <span>Preview not available — use Download</span>
                          )}{' '}
                          <button
                            type="button"
                            className="button"
                            disabled={isPending}
                            onClick={() => {
                              handleAcknowledge(version);
                            }}
                          >
                            Acknowledge
                          </button>{' '}
                          <button
                            type="button"
                            className="button"
                            disabled={isPending}
                            onClick={() => {
                              toggleAcknowledgements(version);
                            }}
                          >
                            {expandedAckVersionId === version.id
                              ? 'Hide who acknowledged'
                              : 'Who acknowledged?'}
                          </button>
                          {version.status === 'draft' && (
                            <>
                              {' '}
                              <button
                                type="button"
                                className="button"
                                disabled={isPending}
                                onClick={() => {
                                  handleSubmitForApproval(version);
                                }}
                              >
                                Submit for approval
                              </button>
                            </>
                          )}
                          {version.status === 'in_review' && isAdmin && (
                            <div className="form-field">
                              <label htmlFor={`review-comments-${version.id}`}>
                                Review comments (required to reject)
                              </label>
                              <input
                                id={`review-comments-${version.id}`}
                                value={reviewComments[version.id] ?? ''}
                                onChange={(event) => {
                                  const { value } = event.target;
                                  setReviewComments((current) => ({
                                    ...current,
                                    [version.id]: value,
                                  }));
                                }}
                              />
                              <button
                                type="button"
                                className="button button--primary"
                                disabled={isPending}
                                onClick={() => {
                                  handleApprove(version);
                                }}
                              >
                                Approve
                              </button>{' '}
                              <button
                                type="button"
                                className="button"
                                disabled={isPending}
                                onClick={() => {
                                  handleReject(version);
                                }}
                              >
                                Reject
                              </button>
                            </div>
                          )}
                          {expandedAckVersionId === version.id && (
                            <div>
                              {acknowledgementsLoading ? (
                                <p role="status">Loading…</p>
                              ) : acknowledgements.length === 0 ? (
                                <p>No one has acknowledged this version yet.</p>
                              ) : (
                                <ul>
                                  {acknowledgements.map((acknowledgement) => (
                                    <li key={acknowledgement.id}>
                                      {acknowledgement.acknowledged_by_id} —{' '}
                                      {acknowledgement.acknowledged_at}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                          {previewVersionId === version.id && (
                            <div>
                              {previewLoading && <p role="status">Loading preview…</p>}
                              {previewError && (
                                <p role="alert" className="auth-form__error">
                                  {previewError}
                                </p>
                              )}
                              {previewUrl &&
                                !previewLoading &&
                                !previewError &&
                                (isImagePreview ? (
                                  <img
                                    src={previewUrl}
                                    alt={`Preview of ${version.original_filename}`}
                                    style={{ maxWidth: '100%' }}
                                  />
                                ) : (
                                  <iframe
                                    src={previewUrl}
                                    title={`Preview of ${version.original_filename}`}
                                    width="100%"
                                    height="480"
                                    sandbox=""
                                  />
                                ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <VersionComparePanel documentId={id} versions={versions} />
        </>
      )}
    </section>
  );
}
