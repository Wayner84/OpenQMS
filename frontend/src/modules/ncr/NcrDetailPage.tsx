import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { useAuth } from '../auth/AuthContext';
import { listDocuments } from '../documents/api';
import type { DocumentRecord } from '../documents/types';
import { listCompanies, listPeople } from '../people/api';
import type { Company, Person } from '../people/types';
import { listProducts } from '../products/api';
import type { Product } from '../products/types';
import { listSuppliers } from '../suppliers/api';
import type { Supplier } from '../suppliers/types';
import {
  createAction,
  createAttachment,
  deleteAttachment,
  deleteNcr,
  exportNcr,
  getInvestigationTool,
  getNcr,
  listActions,
  listAttachments,
  listStatusHistory,
  transitionNcr,
  updateAction,
  updateNcr,
  upsertInvestigationTool,
} from './api';
import type {
  Ncr,
  NcrAction,
  NcrActionStatus,
  NcrAttachment,
  NcrInvestigationTool,
  NcrInvestigationToolType,
  NcrStatusHistoryEntry,
  NcrType,
} from './types';
import { NCR_STATUS_SEQUENCE } from './types';

const TYPE_LABELS: Record<NcrType, string> = {
  internal: 'Internal',
  supplier: 'Supplier',
};

const STATUS_LABELS: Record<Ncr['status'], string> = {
  open: 'Open',
  investigate: 'Investigate',
  containment: 'Containment',
  corrective_action: 'Corrective action',
  verification: 'Verification',
  closed: 'Closed',
};

const TOOL_TYPES: readonly NcrInvestigationToolType[] = [
  'five_why',
  'fishbone',
  'eight_d',
  'ten_d',
];

const TOOL_LABELS: Record<NcrInvestigationToolType, string> = {
  five_why: '5 Why',
  fishbone: 'Fishbone / Ishikawa',
  eight_d: '8D',
  ten_d: '10D',
};

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
  type: NcrType;
  productId: string;
  supplierId: string;
  raisedById: string;
  description: string;
  rootCauseSummary: string;
}

function toMetadataForm(ncr: Ncr): MetadataForm {
  return {
    type: ncr.type,
    productId: ncr.product_id ?? '',
    supplierId: ncr.supplier_id ?? '',
    raisedById: ncr.raised_by_id,
    description: ncr.description,
    rootCauseSummary: ncr.root_cause_summary ?? '',
  };
}

interface ActionForm {
  description: string;
  ownerId: string;
  dueDate: string;
}

const emptyActionForm: ActionForm = { description: '', ownerId: '', dueDate: '' };

function toActionForm(action: NcrAction): ActionForm {
  return {
    description: action.description,
    ownerId: action.owner_id ?? '',
    dueDate: action.due_date ?? '',
  };
}

interface ToolEntry {
  key: string;
  value: string;
}

function toToolEntries(data: Record<string, unknown>): ToolEntry[] {
  return Object.entries(data).map(([key, value]) => ({ key, value: String(value) }));
}

/**
 * A single NCR: metadata (with an edit form), a workflow panel (the single next
 * allowed transition, per design decision 3), status history, actions
 * (add/edit/complete), the four structured investigation tools (a simple
 * key/value worksheet editor, since each tool's `data` shape is intentionally
 * unmodelled at the API layer), attachments (attach an existing document by
 * search, matching Products' document-linking UX), and PDF export, per
 * docs/modules/NCR.md.
 */
export function NcrDetailPage(): ReactElement {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const navigate = useNavigate();

  const [ncr, setNcr] = useState<Ncr | null>(null);
  const [statusHistory, setStatusHistory] = useState<NcrStatusHistoryEntry[]>([]);
  const [actions, setActions] = useState<NcrAction[]>([]);
  const [tools, setTools] = useState<
    Partial<Record<NcrInvestigationToolType, NcrInvestigationTool>>
  >({});
  const [attachments, setAttachments] = useState<NcrAttachment[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [editingMetadata, setEditingMetadata] = useState(false);
  const [metadataForm, setMetadataForm] = useState<MetadataForm>({
    type: 'internal',
    productId: '',
    supplierId: '',
    raisedById: '',
    description: '',
    rootCauseSummary: '',
  });
  const [savingMetadata, setSavingMetadata] = useState(false);

  const [transitionComments, setTransitionComments] = useState('');
  const [transitioning, setTransitioning] = useState(false);

  const [actionForm, setActionForm] = useState<ActionForm>(emptyActionForm);
  const [editingActionId, setEditingActionId] = useState<string | null>(null);
  const [savingAction, setSavingAction] = useState(false);
  const [pendingActionIds, setPendingActionIds] = useState<ReadonlySet<string>>(new Set());

  const [activeToolType, setActiveToolType] = useState<NcrInvestigationToolType>('five_why');
  const [toolEntries, setToolEntries] = useState<ToolEntry[]>([]);
  const [savingTool, setSavingTool] = useState(false);

  const [documentSearchInput, setDocumentSearchInput] = useState('');
  const [documentSearchResults, setDocumentSearchResults] = useState<DocumentRecord[]>([]);
  const [documentSearching, setDocumentSearching] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState('');
  const [attachmentDescription, setAttachmentDescription] = useState('');
  const [linkingAttachment, setLinkingAttachment] = useState(false);
  const [pendingAttachmentIds, setPendingAttachmentIds] = useState<ReadonlySet<string>>(new Set());

  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const mountedRef = useRef(true);
  const currentNcrIdRef = useRef(id);
  const loadRequestIdRef = useRef(0);
  currentNcrIdRef.current = id;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void fetchAllPages<Product>((params) => listProducts(params)).then((items) => {
      if (mountedRef.current) {
        setProducts(items);
      }
    });
    void fetchAllPages<Supplier>((params) => listSuppliers(params)).then((items) => {
      if (mountedRef.current) {
        setSuppliers(items);
      }
    });
    void fetchAllPages<Company>((params) => listCompanies(params)).then((items) => {
      if (mountedRef.current) {
        setCompanies(items);
      }
    });
    void fetchAllPages<Person>((params) => listPeople(params)).then((items) => {
      if (mountedRef.current) {
        setPeople(items);
      }
    });
  }, []);

  const companyNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const company of companies) {
      map.set(company.id, company.name);
    }
    return map;
  }, [companies]);

  const supplierLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const supplier of suppliers) {
      map.set(supplier.id, companyNameById.get(supplier.company_id) ?? supplier.company_id);
    }
    return map;
  }, [suppliers, companyNameById]);

  const productLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const product of products) {
      map.set(product.id, `${product.part_number} — ${product.description}`);
    }
    return map;
  }, [products]);

  const personNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const person of people) {
      map.set(person.id, personDisplayName(person));
    }
    return map;
  }, [people]);

  const loadAll = useCallback(async () => {
    if (!id || currentNcrIdRef.current !== id) {
      return;
    }
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    setLoadError(null);
    try {
      const [ncrResult, historyItems, actionItems, toolResults, attachmentItems] =
        await Promise.all([
          getNcr(id),
          fetchAllPages<NcrStatusHistoryEntry>((params) => listStatusHistory(id, params)),
          fetchAllPages<NcrAction>((params) => listActions(id, params)),
          Promise.all(TOOL_TYPES.map((toolType) => getInvestigationTool(id, toolType))),
          fetchAllPages<NcrAttachment>((params) => listAttachments(id, params)),
        ]);
      if (
        mountedRef.current &&
        currentNcrIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setNcr(ncrResult);
        setStatusHistory(historyItems);
        setActions(actionItems);
        const toolsByType: Partial<Record<NcrInvestigationToolType, NcrInvestigationTool>> = {};
        TOOL_TYPES.forEach((toolType, index) => {
          toolsByType[toolType] = toolResults[index];
        });
        setTools(toolsByType);
        setAttachments(attachmentItems);
      }
    } catch {
      if (
        mountedRef.current &&
        currentNcrIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoadError('Could not load this NCR. Please try again.');
      }
    } finally {
      if (
        mountedRef.current &&
        currentNcrIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoading(false);
      }
    }
  }, [id]);

  useEffect(() => {
    setToolEntries(toToolEntries(tools[activeToolType]?.data ?? {}));
  }, [tools, activeToolType]);

  useEffect(() => {
    setNcr(null);
    setStatusHistory([]);
    setActions([]);
    setTools({});
    setAttachments([]);
    setLoadError(null);
    setActionError(null);
    setEditingMetadata(false);
    setTransitionComments('');
    setActionForm(emptyActionForm);
    setEditingActionId(null);
    setActiveToolType('five_why');
    setToolEntries([]);
    setDocumentSearchInput('');
    setDocumentSearchResults([]);
    setSelectedDocumentId('');
    setAttachmentDescription('');
  }, [id]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const isClosed = ncr?.status === 'closed';
  const nextStatus = useMemo(() => {
    if (!ncr) {
      return null;
    }
    const currentIndex = NCR_STATUS_SEQUENCE.indexOf(ncr.status);
    if (currentIndex === -1 || currentIndex === NCR_STATUS_SEQUENCE.length - 1) {
      return null;
    }
    return NCR_STATUS_SEQUENCE[currentIndex + 1];
  }, [ncr]);

  const startEditMetadata = (): void => {
    if (!ncr) {
      return;
    }
    setActionError(null);
    setMetadataForm(toMetadataForm(ncr));
    setEditingMetadata(true);
  };

  const cancelEditMetadata = (): void => {
    setEditingMetadata(false);
  };

  const handleMetadataSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id) {
      return;
    }
    setActionError(null);
    setSavingMetadata(true);
    const actionNcrId = id;
    void (async () => {
      try {
        await updateNcr(id, {
          type: metadataForm.type,
          product_id: metadataForm.productId || undefined,
          supplier_id:
            metadataForm.type === 'supplier' ? metadataForm.supplierId || undefined : undefined,
          raised_by_id: metadataForm.raisedById,
          description: metadataForm.description,
          root_cause_summary: metadataForm.rootCauseSummary || undefined,
        });
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setEditingMetadata(false);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(getErrorDetail(err) ?? 'Could not save these changes. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setSavingMetadata(false);
        }
      }
    })();
  };

  const handleTransition = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id || !nextStatus) {
      return;
    }
    setActionError(null);
    setTransitioning(true);
    const actionNcrId = id;
    void (async () => {
      try {
        await transitionNcr(id, {
          to_status: nextStatus,
          comments: transitionComments || undefined,
        });
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setTransitionComments('');
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(getErrorDetail(err) ?? 'Could not advance this NCR. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setTransitioning(false);
        }
      }
    })();
  };

  const startEditAction = (action: NcrAction): void => {
    setActionError(null);
    setEditingActionId(action.id);
    setActionForm(toActionForm(action));
  };

  const cancelEditAction = (): void => {
    setEditingActionId(null);
    setActionForm(emptyActionForm);
  };

  const handleActionSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id) {
      return;
    }
    setActionError(null);
    setSavingAction(true);
    const actionNcrId = id;
    void (async () => {
      try {
        if (editingActionId) {
          const existing = actions.find((candidate) => candidate.id === editingActionId);
          await updateAction(editingActionId, {
            description: actionForm.description,
            owner_id: actionForm.ownerId || undefined,
            due_date: actionForm.dueDate || undefined,
            status: existing?.status ?? 'open',
          });
        } else {
          await createAction(id, {
            description: actionForm.description,
            owner_id: actionForm.ownerId || undefined,
            due_date: actionForm.dueDate || undefined,
          });
        }
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionForm(emptyActionForm);
          setEditingActionId(null);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(
            getErrorDetail(err) ??
              `Could not ${editingActionId ? 'update' : 'add'} the action. Please try again.`,
          );
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setSavingAction(false);
        }
      }
    })();
  };

  const handleToggleActionStatus = (action: NcrAction): void => {
    if (!id) {
      return;
    }
    const nextActionStatus: NcrActionStatus = action.status === 'open' ? 'complete' : 'open';
    setActionError(null);
    setPendingActionIds((current) => new Set(current).add(action.id));
    const actionNcrId = id;
    void (async () => {
      try {
        await updateAction(action.id, {
          description: action.description,
          owner_id: action.owner_id ?? undefined,
          due_date: action.due_date ?? undefined,
          status: nextActionStatus,
        });
        if (currentNcrIdRef.current === actionNcrId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(getErrorDetail(err) ?? 'Could not update this action. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setPendingActionIds((current) => {
            const next = new Set(current);
            next.delete(action.id);
            return next;
          });
        }
      }
    })();
  };

  const handleSelectTool = (toolType: NcrInvestigationToolType): void => {
    setActiveToolType(toolType);
  };

  const handleToolEntryChange = (index: number, field: 'key' | 'value', value: string): void => {
    setToolEntries((current) =>
      current.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry,
      ),
    );
  };

  const handleAddToolEntry = (): void => {
    setToolEntries((current) => [...current, { key: '', value: '' }]);
  };

  const handleRemoveToolEntry = (index: number): void => {
    setToolEntries((current) => current.filter((_entry, entryIndex) => entryIndex !== index));
  };

  const handleToolSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id) {
      return;
    }
    setActionError(null);
    setSavingTool(true);
    const actionNcrId = id;
    const data: Record<string, unknown> = {};
    for (const entry of toolEntries) {
      if (entry.key.trim()) {
        data[entry.key.trim()] = entry.value;
      }
    }
    void (async () => {
      try {
        await upsertInvestigationTool(id, activeToolType, data);
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not save this investigation tool. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setSavingTool(false);
        }
      }
    })();
  };

  const handleDocumentSearchSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setActionError(null);
    setDocumentSearching(true);
    void (async () => {
      try {
        const results = await listDocuments({
          search: documentSearchInput || undefined,
          limit: 20,
        });
        if (mountedRef.current) {
          setDocumentSearchResults(results.items);
        }
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not search documents. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setDocumentSearching(false);
        }
      }
    })();
  };

  const handleAttachDocument = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id || !selectedDocumentId) {
      return;
    }
    setActionError(null);
    setLinkingAttachment(true);
    const actionNcrId = id;
    void (async () => {
      try {
        await createAttachment(id, {
          document_id: selectedDocumentId,
          description: attachmentDescription || undefined,
        });
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setSelectedDocumentId('');
          setAttachmentDescription('');
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not attach this document. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setLinkingAttachment(false);
        }
      }
    })();
  };

  const handleRemoveAttachment = (attachment: NcrAttachment): void => {
    if (!id) {
      return;
    }
    setActionError(null);
    setPendingAttachmentIds((current) => new Set(current).add(attachment.id));
    const actionNcrId = id;
    void (async () => {
      try {
        await deleteAttachment(id, attachment.id);
        if (currentNcrIdRef.current === actionNcrId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not remove this attachment. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setPendingAttachmentIds((current) => {
            const next = new Set(current);
            next.delete(attachment.id);
            return next;
          });
        }
      }
    })();
  };

  const handleExport = (): void => {
    if (!id || !ncr) {
      return;
    }
    setActionError(null);
    setExporting(true);
    const actionNcrId = id;
    void (async () => {
      try {
        const blob = await exportNcr(id);
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          triggerBrowserDownload(blob, `${ncr.number}.pdf`);
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(getErrorDetail(err) ?? 'Could not export this NCR. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setExporting(false);
        }
      }
    })();
  };

  const handleDeleteNcr = (): void => {
    if (!id) {
      return;
    }
    if (!window.confirm('Delete this NCR? It will be removed from lists and searches.')) {
      return;
    }
    setActionError(null);
    setDeleting(true);
    const actionNcrId = id;
    void (async () => {
      try {
        await deleteNcr(id);
        if (currentNcrIdRef.current === actionNcrId) {
          void navigate('/ncr');
        }
      } catch (err) {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setActionError(getErrorDetail(err) ?? 'Could not delete this NCR. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentNcrIdRef.current === actionNcrId) {
          setDeleting(false);
        }
      }
    })();
  };

  if (!id) {
    return <p role="alert">No NCR specified.</p>;
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

      {!loading && !loadError && ncr && (
        <>
          <h2>
            {ncr.number} — {TYPE_LABELS[ncr.type]}
          </h2>
          <p>
            Status: {STATUS_LABELS[ncr.status]}
            {' · '}
            Raised by: {personNameById.get(ncr.raised_by_id) ?? ncr.raised_by_id}
            {ncr.product_id && (
              <>
                {' · '}
                Product: {productLabelById.get(ncr.product_id) ?? ncr.product_id}
              </>
            )}
            {ncr.supplier_id && (
              <>
                {' · '}
                Supplier: {supplierLabelById.get(ncr.supplier_id) ?? ncr.supplier_id}
              </>
            )}
          </p>
          {actionError && (
            <p role="alert" className="auth-form__error">
              {actionError}
            </p>
          )}
          {!isClosed && (
            <button
              type="button"
              className="button"
              onClick={editingMetadata ? cancelEditMetadata : startEditMetadata}
            >
              {editingMetadata ? 'Cancel editing' : 'Edit details'}
            </button>
          )}{' '}
          <button type="button" className="button" disabled={exporting} onClick={handleExport}>
            {exporting ? 'Exporting…' : 'Export PDF'}
          </button>{' '}
          {isAdmin && (
            <button type="button" className="button" disabled={deleting} onClick={handleDeleteNcr}>
              {deleting ? 'Deleting…' : 'Delete NCR'}
            </button>
          )}
          {!isClosed && editingMetadata && (
            <form
              className="auth-form"
              onSubmit={handleMetadataSubmit}
              aria-label="Edit NCR details"
            >
              <div className="form-field">
                <label htmlFor="metadata-type">Type</label>
                <select
                  id="metadata-type"
                  value={metadataForm.type}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
                      ...current,
                      type: event.target.value as NcrType,
                    }));
                  }}
                >
                  {(Object.keys(TYPE_LABELS) as NcrType[]).map((type) => (
                    <option key={type} value={type}>
                      {TYPE_LABELS[type]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="metadata-raised-by">Raised by</label>
                <select
                  id="metadata-raised-by"
                  required
                  value={metadataForm.raisedById}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
                      ...current,
                      raisedById: event.target.value,
                    }));
                  }}
                >
                  <option value="">Choose a person</option>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {personDisplayName(person)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="metadata-product">Product (optional)</label>
                <select
                  id="metadata-product"
                  value={metadataForm.productId}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
                      ...current,
                      productId: event.target.value,
                    }));
                  }}
                >
                  <option value="">No product</option>
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {productLabelById.get(product.id) ?? product.id}
                    </option>
                  ))}
                </select>
              </div>
              {metadataForm.type === 'supplier' && (
                <div className="form-field">
                  <label htmlFor="metadata-supplier">Supplier</label>
                  <select
                    id="metadata-supplier"
                    required
                    value={metadataForm.supplierId}
                    onChange={(event) => {
                      setMetadataForm((current) => ({
                        ...current,
                        supplierId: event.target.value,
                      }));
                    }}
                  >
                    <option value="">Choose a supplier</option>
                    {suppliers.map((supplier) => (
                      <option key={supplier.id} value={supplier.id}>
                        {supplierLabelById.get(supplier.id) ?? supplier.id}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="form-field">
                <label htmlFor="metadata-description">Description</label>
                <textarea
                  id="metadata-description"
                  required
                  value={metadataForm.description}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
                      ...current,
                      description: event.target.value,
                    }));
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="metadata-root-cause">Root cause summary</label>
                <textarea
                  id="metadata-root-cause"
                  value={metadataForm.rootCauseSummary}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
                      ...current,
                      rootCauseSummary: event.target.value,
                    }));
                  }}
                />
              </div>
              <button type="submit" className="button button--primary" disabled={savingMetadata}>
                {savingMetadata ? 'Saving…' : 'Save changes'}
              </button>{' '}
              <button type="button" className="button" onClick={cancelEditMetadata}>
                Cancel
              </button>
            </form>
          )}
          <h3>Workflow</h3>
          {isClosed ? (
            <p>
              This NCR is closed. Its details, actions, investigation tools, and attachments are
              frozen.
            </p>
          ) : nextStatus ? (
            <form className="auth-form" onSubmit={handleTransition} aria-label="Advance workflow">
              <div className="form-field">
                <label htmlFor="transition-comments">Comments (optional)</label>
                <textarea
                  id="transition-comments"
                  value={transitionComments}
                  onChange={(event) => {
                    setTransitionComments(event.target.value);
                  }}
                />
              </div>
              <button type="submit" className="button button--primary" disabled={transitioning}>
                {transitioning ? 'Advancing…' : `Advance to ${STATUS_LABELS[nextStatus]}`}
              </button>
            </form>
          ) : null}
          <h3>Status history</h3>
          {statusHistory.length === 0 ? (
            <p>No status history yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">From</th>
                    <th scope="col">To</th>
                    <th scope="col">Changed at</th>
                    <th scope="col">Comments</th>
                  </tr>
                </thead>
                <tbody>
                  {statusHistory.map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.from_status ? STATUS_LABELS[entry.from_status] : '—'}</td>
                      <td>{STATUS_LABELS[entry.to_status]}</td>
                      <td>{entry.changed_at}</td>
                      <td>{entry.comments}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <h3>Actions</h3>
          {!isClosed && (
            <form
              className="auth-form"
              onSubmit={handleActionSubmit}
              aria-label={editingActionId ? 'Edit action' : 'Add action'}
            >
              <div className="form-field">
                <label htmlFor="action-description">Action description</label>
                <input
                  id="action-description"
                  required
                  value={actionForm.description}
                  onChange={(event) => {
                    setActionForm((current) => ({ ...current, description: event.target.value }));
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="action-owner">Owner (optional)</label>
                <select
                  id="action-owner"
                  value={actionForm.ownerId}
                  onChange={(event) => {
                    setActionForm((current) => ({ ...current, ownerId: event.target.value }));
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
              <div className="form-field">
                <label htmlFor="action-due-date">Due date (optional)</label>
                <input
                  id="action-due-date"
                  type="date"
                  value={actionForm.dueDate}
                  onChange={(event) => {
                    setActionForm((current) => ({ ...current, dueDate: event.target.value }));
                  }}
                />
              </div>
              <button type="submit" className="button button--primary" disabled={savingAction}>
                {savingAction ? 'Saving…' : editingActionId ? 'Save changes' : 'Add action'}
              </button>{' '}
              {editingActionId && (
                <button type="button" className="button" onClick={cancelEditAction}>
                  Cancel
                </button>
              )}
            </form>
          )}
          {actions.length === 0 ? (
            <p>No actions recorded yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Description</th>
                    <th scope="col">Owner</th>
                    <th scope="col">Due date</th>
                    <th scope="col">Status</th>
                    {!isClosed && <th scope="col">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {actions.map((action) => {
                    const isPending = pendingActionIds.has(action.id);
                    return (
                      <tr key={action.id}>
                        <td>{action.description}</td>
                        <td>
                          {action.owner_id
                            ? (personNameById.get(action.owner_id) ?? action.owner_id)
                            : 'Unassigned'}
                        </td>
                        <td>{action.due_date ?? 'Not set'}</td>
                        <td>{action.status === 'open' ? 'Open' : 'Complete'}</td>
                        {!isClosed && (
                          <td>
                            <button
                              type="button"
                              className="button"
                              disabled={isPending}
                              onClick={() => {
                                startEditAction(action);
                              }}
                            >
                              Edit
                            </button>{' '}
                            <button
                              type="button"
                              className="button"
                              disabled={isPending}
                              onClick={() => {
                                handleToggleActionStatus(action);
                              }}
                            >
                              {action.status === 'open' ? 'Complete' : 'Reopen'}
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <h3>Investigation tools</h3>
          <div className="app-header__actions" role="tablist" aria-label="Investigation tools">
            {TOOL_TYPES.map((toolType) => (
              <button
                key={toolType}
                type="button"
                role="tab"
                aria-selected={activeToolType === toolType}
                className="button"
                onClick={() => {
                  handleSelectTool(toolType);
                }}
              >
                {TOOL_LABELS[toolType]}
              </button>
            ))}
          </div>
          {!isClosed ? (
            <form
              className="auth-form"
              onSubmit={handleToolSubmit}
              aria-label={`${TOOL_LABELS[activeToolType]} worksheet`}
            >
              {toolEntries.length === 0 && <p>No entries yet.</p>}
              {toolEntries.map((entry, index) => (
                <div className="form-field" key={index}>
                  <label htmlFor={`tool-entry-key-${index}`}>Field</label>
                  <input
                    id={`tool-entry-key-${index}`}
                    value={entry.key}
                    onChange={(event) => {
                      handleToolEntryChange(index, 'key', event.target.value);
                    }}
                  />
                  <label htmlFor={`tool-entry-value-${index}`}>Value</label>
                  <input
                    id={`tool-entry-value-${index}`}
                    value={entry.value}
                    onChange={(event) => {
                      handleToolEntryChange(index, 'value', event.target.value);
                    }}
                  />
                  <button
                    type="button"
                    className="button"
                    onClick={() => {
                      handleRemoveToolEntry(index);
                    }}
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button type="button" className="button" onClick={handleAddToolEntry}>
                Add field
              </button>{' '}
              <button type="submit" className="button button--primary" disabled={savingTool}>
                {savingTool ? 'Saving…' : 'Save worksheet'}
              </button>
            </form>
          ) : toolEntries.length === 0 ? (
            <p>Not started.</p>
          ) : (
            <ul>
              {toolEntries.map((entry) => (
                <li key={entry.key}>
                  <strong>{entry.key}:</strong> {entry.value}
                </li>
              ))}
            </ul>
          )}
          <h3>Attachments</h3>
          {attachments.length === 0 ? (
            <p>No attachments yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Document</th>
                    <th scope="col">Description</th>
                    {!isClosed && <th scope="col">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {attachments.map((attachment) => {
                    const isPending = pendingAttachmentIds.has(attachment.id);
                    return (
                      <tr key={attachment.id}>
                        <td>{attachment.document_id}</td>
                        <td>{attachment.description}</td>
                        {!isClosed && (
                          <td>
                            <button
                              type="button"
                              className="button"
                              disabled={isPending}
                              onClick={() => {
                                handleRemoveAttachment(attachment);
                              }}
                            >
                              Remove
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {!isClosed && (
            <>
              <form
                role="search"
                aria-label="Search documents to attach"
                onSubmit={handleDocumentSearchSubmit}
              >
                <div className="form-field">
                  <label htmlFor="attachment-document-search">Search documents</label>
                  <input
                    id="attachment-document-search"
                    type="search"
                    value={documentSearchInput}
                    onChange={(event) => {
                      setDocumentSearchInput(event.target.value);
                    }}
                  />
                </div>
                <button type="submit" className="button" disabled={documentSearching}>
                  {documentSearching ? 'Searching…' : 'Search'}
                </button>
              </form>

              {documentSearchResults.length > 0 && (
                <form
                  className="auth-form"
                  onSubmit={handleAttachDocument}
                  aria-label="Attach document"
                >
                  <div className="form-field">
                    <label htmlFor="attachment-document-select">Document</label>
                    <select
                      id="attachment-document-select"
                      required
                      value={selectedDocumentId}
                      onChange={(event) => {
                        setSelectedDocumentId(event.target.value);
                      }}
                    >
                      <option value="">Choose a document</option>
                      {documentSearchResults.map((document) => (
                        <option key={document.id} value={document.id}>
                          {document.number} — {document.title}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-field">
                    <label htmlFor="attachment-description">Description (optional)</label>
                    <input
                      id="attachment-description"
                      value={attachmentDescription}
                      onChange={(event) => {
                        setAttachmentDescription(event.target.value);
                      }}
                    />
                  </div>
                  <button
                    type="submit"
                    className="button button--primary"
                    disabled={linkingAttachment}
                  >
                    {linkingAttachment ? 'Attaching…' : 'Attach document'}
                  </button>
                </form>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
