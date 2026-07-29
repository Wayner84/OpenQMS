import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createProduct, listProductCategories, listProducts } from './api';
import { ProductsPage } from './ProductsPage';

vi.mock('./api');

const mockedListProducts = vi.mocked(listProducts);
const mockedCreateProduct = vi.mocked(createProduct);
const mockedListProductCategories = vi.mocked(listProductCategories);

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

function renderPage(pageSize?: number): ReturnType<typeof render> {
  return render(
    <MemoryRouter>
      <ProductsPage pageSize={pageSize} />
    </MemoryRouter>,
  );
}

describe('ProductsPage', () => {
  beforeEach(() => {
    mockedListProductCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the list of products', async () => {
    mockedListProducts.mockResolvedValue({ items: [bolt], total: 1, limit: 20, offset: 0 });

    renderPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'BOLT-001' })).toBeInTheDocument();
    });
    expect(screen.getByText('M6 bolt')).toBeInTheDocument();
  });

  it('loads the list under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    mockedListProducts.mockResolvedValue({ items: [bolt], total: 1, limit: 20, offset: 0 });

    render(
      <StrictMode>
        <MemoryRouter>
          <ProductsPage />
        </MemoryRouter>
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'BOLT-001' })).toBeInTheDocument();
    });
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListProducts.mockRejectedValue(new Error('network error'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load products/i);
  });

  it('creates a product and refreshes the list', async () => {
    mockedListProducts.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });
    mockedCreateProduct.mockResolvedValue(bolt);
    mockedListProducts.mockResolvedValueOnce({ items: [bolt], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/part number/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/part number/i), { target: { value: 'BOLT-001' } });
    fireEvent.change(screen.getByLabelText(/^description$/i), { target: { value: 'M6 bolt' } });
    fireEvent.click(screen.getByRole('button', { name: /^create product$/i }));

    await waitFor(() => {
      expect(mockedCreateProduct).toHaveBeenCalledWith(
        expect.objectContaining({ part_number: 'BOLT-001', description: 'M6 bolt' }),
      );
    });
  });

  it('searches products by part number or description', async () => {
    mockedListProducts.mockResolvedValue({ items: [bolt], total: 1, limit: 20, offset: 0 });

    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'BOLT-001' })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/^search$/i), { target: { value: 'bolt' } });
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      expect(mockedListProducts).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'bolt' }),
      );
    });
  });

  it('links to category administration', async () => {
    mockedListProducts.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    renderPage();

    expect(await screen.findByRole('link', { name: /manage categories/i })).toHaveAttribute(
      'href',
      '/products/categories',
    );
  });

  it('paginates using the total count', async () => {
    const bracket = { ...bolt, id: 'p2', part_number: 'BRACKET-001' };
    mockedListProducts.mockResolvedValueOnce({ items: [bolt], total: 2, limit: 1, offset: 0 });
    mockedListProducts.mockResolvedValueOnce({ items: [bracket], total: 2, limit: 1, offset: 1 });

    renderPage(1);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'BOLT-001' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'BRACKET-001' })).toBeInTheDocument();
    });
  });
});
