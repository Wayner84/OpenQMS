import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listDocuments } from '../documents/api';
import { listCompanies } from '../people/api';
import { listSuppliers } from '../suppliers/api';
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
import { ProductDetailPage } from './ProductDetailPage';

vi.mock('./api');
vi.mock('../documents/api');
vi.mock('../people/api');
vi.mock('../suppliers/api');

const mockedGetProduct = vi.mocked(getProduct);
const mockedUpdateProduct = vi.mocked(updateProduct);
const mockedListProductCategories = vi.mocked(listProductCategories);
const mockedListProductDocumentLinks = vi.mocked(listProductDocumentLinks);
const mockedCreateProductDocumentLink = vi.mocked(createProductDocumentLink);
const mockedDeleteProductDocumentLink = vi.mocked(deleteProductDocumentLink);
const mockedListProductSupplierLinks = vi.mocked(listProductSupplierLinks);
const mockedCreateProductSupplierLink = vi.mocked(createProductSupplierLink);
const mockedDeleteProductSupplierLink = vi.mocked(deleteProductSupplierLink);
const mockedListDocuments = vi.mocked(listDocuments);
const mockedListCompanies = vi.mocked(listCompanies);
const mockedListSuppliers = vi.mocked(listSuppliers);

const bolt = {
  id: 'p1',
  organisation_id: 'o1',
  part_number: 'BOLT-001',
  description: 'M6 bolt',
  revision: 'A',
  category_id: null,
  type: 'purchased' as const,
  manufacturing_notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const drawing = {
  id: 'd1',
  organisation_id: 'o1',
  category_id: null,
  number: 'DOC-0001',
  title: 'Bolt Drawing',
  owner_id: null,
  status: 'approved' as const,
  current_version_id: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
  tags: [],
};

const acmeCompany = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Acme Ltd',
  type: 'supplier' as const,
  address: null,
  phone: null,
  general_email: null,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const acmeSupplier = {
  id: 's1',
  organisation_id: 'o1',
  company_id: 'c1',
  approval_status: 'approved' as const,
  risk_rating: 'low' as const,
  is_preferred: false,
  notes: null,
  created_by_id: 'u1',
  updated_by_id: 'u1',
};

const documentLink = {
  id: 'link1',
  product_id: 'p1',
  document_id: 'd1',
  relationship_type: 'drawing' as const,
};

const supplierLink = { id: 'slink1', product_id: 'p1', supplier_id: 's1', is_preferred: false };

function renderPage(productId = 'p1', wrapInStrictMode = false): ReturnType<typeof render> {
  const routes = (
    <MemoryRouter initialEntries={[`/products/${productId}`]}>
      <Routes>
        <Route path="/products/:id" element={<ProductDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
  return render(wrapInStrictMode ? <StrictMode>{routes}</StrictMode> : routes);
}

describe('ProductDetailPage', () => {
  beforeEach(() => {
    mockedGetProduct.mockResolvedValue(bolt);
    mockedListProductCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListProductDocumentLinks.mockResolvedValue({
      items: [documentLink],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListProductSupplierLinks.mockResolvedValue({
      items: [supplierLink],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListCompanies.mockResolvedValue({
      items: [acmeCompany],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListSuppliers.mockResolvedValue({
      items: [acmeSupplier],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListDocuments.mockResolvedValue({ items: [drawing], total: 1, limit: 20, offset: 0 });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the product metadata and links', async () => {
    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /bolt-001/i })).toBeInTheDocument();
    });
    expect(screen.getByText('d1')).toBeInTheDocument();
    expect(screen.getAllByText('Acme Ltd').length).toBeGreaterThan(0);
  });

  it('loads under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    renderPage('p1', true);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /bolt-001/i })).toBeInTheDocument();
    });
  });

  it('shows an error message when the product fails to load', async () => {
    mockedGetProduct.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load this product/i);
  });

  it('edits product metadata', async () => {
    mockedUpdateProduct.mockResolvedValue({ ...bolt, description: 'M6 stainless bolt' });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /bolt-001/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit details/i }));
    fireEvent.change(screen.getByLabelText(/^description$/i), {
      target: { value: 'M6 stainless bolt' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mockedUpdateProduct).toHaveBeenCalledWith(
        'p1',
        expect.objectContaining({ description: 'M6 stainless bolt' }),
      );
    });
  });

  it('searches for and links a document', async () => {
    mockedListProductDocumentLinks.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 200,
      offset: 0,
    });
    mockedCreateProductDocumentLink.mockResolvedValue(documentLink);
    mockedListProductDocumentLinks.mockResolvedValueOnce({
      items: [documentLink],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/^search documents$/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^search documents$/i), { target: { value: 'bolt' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/^document$/i)).toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText(/^document$/i), { target: { value: 'd1' } });
    fireEvent.click(screen.getByRole('button', { name: /link document/i }));

    await waitFor(() => {
      expect(mockedCreateProductDocumentLink).toHaveBeenCalledWith('p1', 'd1', 'drawing');
    });
  });

  it('unlinks a document', async () => {
    mockedDeleteProductDocumentLink.mockResolvedValue(undefined);

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'd1' })).toBeInTheDocument();
    });

    const row = screen.getByRole('cell', { name: 'd1' }).closest('tr');
    expect(row).not.toBeNull();
    fireEvent.click(within(row as HTMLElement).getByRole('button', { name: /unlink/i }));

    await waitFor(() => {
      expect(mockedDeleteProductDocumentLink).toHaveBeenCalledWith('p1', 'link1');
    });
  });

  it('links a supplier', async () => {
    mockedListProductSupplierLinks.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 200,
      offset: 0,
    });
    mockedCreateProductSupplierLink.mockResolvedValue(supplierLink);
    mockedListProductSupplierLinks.mockResolvedValueOnce({
      items: [supplierLink],
      total: 1,
      limit: 200,
      offset: 0,
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/^supplier$/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^supplier$/i), { target: { value: 's1' } });
    fireEvent.click(screen.getByRole('button', { name: /^link supplier$/i }));

    await waitFor(() => {
      expect(mockedCreateProductSupplierLink).toHaveBeenCalledWith('p1', 's1', false);
    });
  });

  it('unlinks a supplier', async () => {
    mockedDeleteProductSupplierLink.mockResolvedValue(undefined);

    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText('Acme Ltd').length).toBeGreaterThan(0);
    });

    const row = screen.getByRole('cell', { name: 'Acme Ltd' }).closest('tr');
    expect(row).not.toBeNull();
    fireEvent.click(within(row as HTMLElement).getByRole('button', { name: /unlink/i }));

    await waitFor(() => {
      expect(mockedDeleteProductSupplierLink).toHaveBeenCalledWith('p1', 'slink1');
    });
  });
});
