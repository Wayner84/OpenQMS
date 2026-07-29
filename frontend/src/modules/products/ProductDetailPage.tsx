import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { useParams } from 'react-router-dom';

import { getErrorDetail } from '../../shared/api/client';
import { fetchAllPages } from '../../shared/api/pagination';
import { listDocuments } from '../documents/api';
import type { DocumentRecord } from '../documents/types';
import { listCompanies } from '../people/api';
import type { Company } from '../people/types';
import { listSuppliers } from '../suppliers/api';
import type { Supplier } from '../suppliers/types';
import {
  createProductDocumentLink,
  createProductSupplierLink,
  deleteProductDocumentLink,
  deleteProductSupplierLink,
  getProduct,
  listProductCategories,
  listProductDocumentLinks,
  listProductSupplierLinks,
  updateProduct,
} from './api';
import type {
  Product,
  ProductCategory,
  ProductDocumentLink,
  ProductDocumentRelationshipType,
  ProductSupplierLink,
  ProductType,
} from './types';

const TYPE_LABELS: Record<ProductType, string> = {
  internal: 'Internal',
  purchased: 'Purchased',
  assembly: 'Assembly',
  component: 'Component',
};

const RELATIONSHIP_TYPE_LABELS: Record<ProductDocumentRelationshipType, string> = {
  drawing: 'Drawing',
  specification: 'Specification',
  cad: 'CAD',
};

interface MetadataForm {
  partNumber: string;
  description: string;
  revision: string;
  categoryId: string;
  type: ProductType;
  manufacturingNotes: string;
}

function toMetadataForm(product: Product): MetadataForm {
  return {
    partNumber: product.part_number,
    description: product.description,
    revision: product.revision,
    categoryId: product.category_id ?? '',
    type: product.type,
    manufacturingNotes: product.manufacturing_notes ?? '',
  };
}

/**
 * A single product: metadata (with an edit form), linked Document Management
 * records (attach an existing document by search, with a relationship type; remove
 * a link), and linked suppliers (attach/remove, showing `is_preferred`), per
 * docs/modules/Products.md.
 */
export function ProductDetailPage(): ReactElement {
  const { id } = useParams<{ id: string }>();

  const [product, setProduct] = useState<Product | null>(null);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [documentLinks, setDocumentLinks] = useState<ProductDocumentLink[]>([]);
  const [supplierLinks, setSupplierLinks] = useState<ProductSupplierLink[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [editingMetadata, setEditingMetadata] = useState(false);
  const [metadataForm, setMetadataForm] = useState<MetadataForm>({
    partNumber: '',
    description: '',
    revision: '',
    categoryId: '',
    type: 'internal',
    manufacturingNotes: '',
  });
  const [savingMetadata, setSavingMetadata] = useState(false);

  const [documentSearchInput, setDocumentSearchInput] = useState('');
  const [documentSearchResults, setDocumentSearchResults] = useState<DocumentRecord[]>([]);
  const [documentSearching, setDocumentSearching] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState('');
  const [relationshipType, setRelationshipType] =
    useState<ProductDocumentRelationshipType>('drawing');
  const [linkingDocument, setLinkingDocument] = useState(false);
  const [pendingDocumentLinkIds, setPendingDocumentLinkIds] = useState<ReadonlySet<string>>(
    new Set(),
  );

  const [selectedSupplierId, setSelectedSupplierId] = useState('');
  const [supplierIsPreferred, setSupplierIsPreferred] = useState(false);
  const [linkingSupplier, setLinkingSupplier] = useState(false);
  const [pendingSupplierLinkIds, setPendingSupplierLinkIds] = useState<ReadonlySet<string>>(
    new Set(),
  );

  const mountedRef = useRef(true);
  const currentProductIdRef = useRef(id);
  const loadRequestIdRef = useRef(0);
  currentProductIdRef.current = id;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void fetchAllPages<ProductCategory>((params) => listProductCategories(params)).then((items) => {
      if (mountedRef.current) {
        setCategories(items);
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
  }, []);

  const categoryNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const category of categories) {
      map.set(category.id, category.name);
    }
    return map;
  }, [categories]);

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

  const loadAll = useCallback(async () => {
    if (!id || currentProductIdRef.current !== id) {
      return;
    }
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    setLoadError(null);
    try {
      const [productResult, documentLinkItems, supplierLinkItems] = await Promise.all([
        getProduct(id),
        fetchAllPages<ProductDocumentLink>((params) => listProductDocumentLinks(id, params)),
        fetchAllPages<ProductSupplierLink>((params) => listProductSupplierLinks(id, params)),
      ]);
      if (
        mountedRef.current &&
        currentProductIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setProduct(productResult);
        setDocumentLinks(documentLinkItems);
        setSupplierLinks(supplierLinkItems);
      }
    } catch {
      if (
        mountedRef.current &&
        currentProductIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoadError('Could not load this product. Please try again.');
      }
    } finally {
      if (
        mountedRef.current &&
        currentProductIdRef.current === id &&
        loadRequestIdRef.current === requestId
      ) {
        setLoading(false);
      }
    }
  }, [id]);

  useEffect(() => {
    setProduct(null);
    setDocumentLinks([]);
    setSupplierLinks([]);
    setLoadError(null);
    setActionError(null);
    setEditingMetadata(false);
    setDocumentSearchInput('');
    setDocumentSearchResults([]);
    setSelectedDocumentId('');
    setSelectedSupplierId('');
    setSupplierIsPreferred(false);
  }, [id]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const startEditMetadata = (): void => {
    if (!product) {
      return;
    }
    setActionError(null);
    setMetadataForm(toMetadataForm(product));
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
    const actionProductId = id;
    void (async () => {
      try {
        await updateProduct(id, {
          part_number: metadataForm.partNumber,
          description: metadataForm.description,
          revision: metadataForm.revision,
          category_id: metadataForm.categoryId || undefined,
          type: metadataForm.type,
          manufacturing_notes: metadataForm.manufacturingNotes || undefined,
        });
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setEditingMetadata(false);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setActionError(getErrorDetail(err) ?? 'Could not save these changes. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setSavingMetadata(false);
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

  const handleLinkDocument = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id || !selectedDocumentId) {
      return;
    }
    setActionError(null);
    setLinkingDocument(true);
    const actionProductId = id;
    void (async () => {
      try {
        await createProductDocumentLink(id, selectedDocumentId, relationshipType);
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setSelectedDocumentId('');
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setActionError(getErrorDetail(err) ?? 'Could not link this document. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setLinkingDocument(false);
        }
      }
    })();
  };

  const handleUnlinkDocument = (link: ProductDocumentLink): void => {
    if (!id) {
      return;
    }
    setActionError(null);
    setPendingDocumentLinkIds((current) => new Set(current).add(link.id));
    const actionProductId = id;
    void (async () => {
      try {
        await deleteProductDocumentLink(id, link.id);
        if (currentProductIdRef.current === actionProductId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not unlink this document. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setPendingDocumentLinkIds((current) => {
            const next = new Set(current);
            next.delete(link.id);
            return next;
          });
        }
      }
    })();
  };

  const handleLinkSupplier = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!id || !selectedSupplierId) {
      return;
    }
    setActionError(null);
    setLinkingSupplier(true);
    const actionProductId = id;
    void (async () => {
      try {
        await createProductSupplierLink(id, selectedSupplierId, supplierIsPreferred);
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setSelectedSupplierId('');
          setSupplierIsPreferred(false);
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setActionError(getErrorDetail(err) ?? 'Could not link this supplier. Please try again.');
        }
      } finally {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setLinkingSupplier(false);
        }
      }
    })();
  };

  const handleUnlinkSupplier = (link: ProductSupplierLink): void => {
    if (!id) {
      return;
    }
    setActionError(null);
    setPendingSupplierLinkIds((current) => new Set(current).add(link.id));
    const actionProductId = id;
    void (async () => {
      try {
        await deleteProductSupplierLink(id, link.id);
        if (currentProductIdRef.current === actionProductId) {
          await loadAll();
        }
      } catch (err) {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setActionError(
            getErrorDetail(err) ?? 'Could not unlink this supplier. Please try again.',
          );
        }
      } finally {
        if (mountedRef.current && currentProductIdRef.current === actionProductId) {
          setPendingSupplierLinkIds((current) => {
            const next = new Set(current);
            next.delete(link.id);
            return next;
          });
        }
      }
    })();
  };

  if (!id) {
    return <p role="alert">No product specified.</p>;
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

      {!loading && !loadError && product && (
        <>
          <h2>
            {product.part_number} — {product.description}
          </h2>
          <p>
            Revision: {product.revision}
            {' · '}
            Category:{' '}
            {product.category_id
              ? (categoryNameById.get(product.category_id) ?? product.category_id)
              : 'None'}
            {' · '}
            Type: {TYPE_LABELS[product.type]}
          </p>
          {actionError && (
            <p role="alert" className="auth-form__error">
              {actionError}
            </p>
          )}
          <button
            type="button"
            className="button"
            onClick={editingMetadata ? cancelEditMetadata : startEditMetadata}
          >
            {editingMetadata ? 'Cancel editing' : 'Edit details'}
          </button>
          {editingMetadata && (
            <form
              className="auth-form"
              onSubmit={handleMetadataSubmit}
              aria-label="Edit product details"
            >
              <div className="form-field">
                <label htmlFor="metadata-part-number">Part number</label>
                <input
                  id="metadata-part-number"
                  required
                  value={metadataForm.partNumber}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, partNumber: event.target.value }));
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="metadata-description">Description</label>
                <input
                  id="metadata-description"
                  required
                  value={metadataForm.description}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, description: event.target.value }));
                  }}
                />
              </div>
              <div className="form-field">
                <label htmlFor="metadata-revision">Revision</label>
                <input
                  id="metadata-revision"
                  value={metadataForm.revision}
                  onChange={(event) => {
                    setMetadataForm((current) => ({ ...current, revision: event.target.value }));
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
                <label htmlFor="metadata-type">Type</label>
                <select
                  id="metadata-type"
                  value={metadataForm.type}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
                      ...current,
                      type: event.target.value as ProductType,
                    }));
                  }}
                >
                  {(Object.keys(TYPE_LABELS) as ProductType[]).map((type) => (
                    <option key={type} value={type}>
                      {TYPE_LABELS[type]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="metadata-manufacturing-notes">Manufacturing notes</label>
                <textarea
                  id="metadata-manufacturing-notes"
                  value={metadataForm.manufacturingNotes}
                  onChange={(event) => {
                    setMetadataForm((current) => ({
                      ...current,
                      manufacturingNotes: event.target.value,
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

          <h3>Linked documents</h3>
          {documentLinks.length === 0 ? (
            <p>No documents linked yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Document</th>
                    <th scope="col">Relationship</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documentLinks.map((link) => {
                    const isPending = pendingDocumentLinkIds.has(link.id);
                    return (
                      <tr key={link.id}>
                        <td>{link.document_id}</td>
                        <td>{RELATIONSHIP_TYPE_LABELS[link.relationship_type]}</td>
                        <td>
                          <button
                            type="button"
                            className="button"
                            disabled={isPending}
                            onClick={() => {
                              handleUnlinkDocument(link);
                            }}
                          >
                            Unlink
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <form
            role="search"
            aria-label="Search documents to link"
            onSubmit={handleDocumentSearchSubmit}
          >
            <div className="form-field">
              <label htmlFor="document-search">Search documents</label>
              <input
                id="document-search"
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
            <form className="auth-form" onSubmit={handleLinkDocument} aria-label="Link document">
              <div className="form-field">
                <label htmlFor="document-select">Document</label>
                <select
                  id="document-select"
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
                <label htmlFor="relationship-type">Relationship type</label>
                <select
                  id="relationship-type"
                  value={relationshipType}
                  onChange={(event) => {
                    setRelationshipType(event.target.value as ProductDocumentRelationshipType);
                  }}
                >
                  {(Object.keys(RELATIONSHIP_TYPE_LABELS) as ProductDocumentRelationshipType[]).map(
                    (type) => (
                      <option key={type} value={type}>
                        {RELATIONSHIP_TYPE_LABELS[type]}
                      </option>
                    ),
                  )}
                </select>
              </div>
              <button type="submit" className="button button--primary" disabled={linkingDocument}>
                {linkingDocument ? 'Linking…' : 'Link document'}
              </button>
            </form>
          )}

          <h3>Linked suppliers</h3>
          {supplierLinks.length === 0 ? (
            <p>No suppliers linked yet.</p>
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Supplier</th>
                    <th scope="col">Preferred</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {supplierLinks.map((link) => {
                    const isPending = pendingSupplierLinkIds.has(link.id);
                    return (
                      <tr key={link.id}>
                        <td>{supplierLabelById.get(link.supplier_id) ?? link.supplier_id}</td>
                        <td>{link.is_preferred ? 'Yes' : 'No'}</td>
                        <td>
                          <button
                            type="button"
                            className="button"
                            disabled={isPending}
                            onClick={() => {
                              handleUnlinkSupplier(link);
                            }}
                          >
                            Unlink
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {suppliers.length > 0 && (
            <form className="auth-form" onSubmit={handleLinkSupplier} aria-label="Link supplier">
              <div className="form-field">
                <label htmlFor="supplier-select">Supplier</label>
                <select
                  id="supplier-select"
                  required
                  value={selectedSupplierId}
                  onChange={(event) => {
                    setSelectedSupplierId(event.target.value);
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
              <div className="form-field">
                <label htmlFor="supplier-preferred">
                  <input
                    id="supplier-preferred"
                    type="checkbox"
                    checked={supplierIsPreferred}
                    onChange={(event) => {
                      setSupplierIsPreferred(event.target.checked);
                    }}
                  />{' '}
                  Preferred
                </label>
              </div>
              <button type="submit" className="button button--primary" disabled={linkingSupplier}>
                {linkingSupplier ? 'Linking…' : 'Link supplier'}
              </button>
            </form>
          )}
        </>
      )}
    </section>
  );
}
