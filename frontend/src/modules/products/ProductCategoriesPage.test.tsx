import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import {
  createProductCategory,
  deleteProductCategory,
  listProductCategories,
  updateProductCategory,
} from './api';
import { ProductCategoriesPage } from './ProductCategoriesPage';

vi.mock('./api');

const mockedListProductCategories = vi.mocked(listProductCategories);
const mockedCreateProductCategory = vi.mocked(createProductCategory);
const mockedUpdateProductCategory = vi.mocked(updateProductCategory);
const mockedDeleteProductCategory = vi.mocked(deleteProductCategory);

const fasteners = { id: 'cat1', organisation_id: 'o1', name: 'Fasteners' };
const electronics = { id: 'cat2', organisation_id: 'o1', name: 'Electronics' };

describe('ProductCategoriesPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the list of categories', async () => {
    mockedListProductCategories.mockResolvedValue({
      items: [fasteners, electronics],
      total: 2,
      limit: 50,
      offset: 0,
    });

    render(<ProductCategoriesPage />);

    expect(screen.getByRole('status')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Fasteners')).toBeInTheDocument();
    });
    expect(screen.getByText('Electronics')).toBeInTheDocument();
  });

  it('loads the list under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    mockedListProductCategories.mockResolvedValue({
      items: [fasteners],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(
      <StrictMode>
        <ProductCategoriesPage />
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByText('Fasteners')).toBeInTheDocument();
    });
  });

  it('shows an error message when the list fails to load', async () => {
    mockedListProductCategories.mockRejectedValue(new Error('network error'));

    render(<ProductCategoriesPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not load product categories/i,
    );
  });

  it('creates a category and refreshes the list', async () => {
    mockedListProductCategories.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    mockedCreateProductCategory.mockResolvedValue(fasteners);
    mockedListProductCategories.mockResolvedValueOnce({
      items: [fasteners],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(<ProductCategoriesPage />);
    await waitFor(() => {
      expect(mockedListProductCategories).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Fasteners' } });
    fireEvent.click(screen.getByRole('button', { name: /^create category$/i }));

    await waitFor(() => {
      expect(screen.getByText('Fasteners')).toBeInTheDocument();
    });
    expect(mockedCreateProductCategory).toHaveBeenCalledWith({ name: 'Fasteners' });
  });

  it('edits a category and refreshes the list', async () => {
    mockedListProductCategories.mockResolvedValueOnce({
      items: [fasteners],
      total: 1,
      limit: 50,
      offset: 0,
    });
    mockedUpdateProductCategory.mockResolvedValue({ ...fasteners, name: 'Hardware' });
    mockedListProductCategories.mockResolvedValueOnce({
      items: [{ ...fasteners, name: 'Hardware' }],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(<ProductCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByText('Fasteners')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit fasteners/i }));
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Hardware' } });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByText('Hardware')).toBeInTheDocument();
    });
    expect(mockedUpdateProductCategory).toHaveBeenCalledWith('cat1', { name: 'Hardware' });
  });

  it('shows the server conflict message inline when deleting an in-use category fails', async () => {
    mockedListProductCategories.mockResolvedValue({
      items: [fasteners],
      total: 1,
      limit: 50,
      offset: 0,
    });
    mockedDeleteProductCategory.mockRejectedValue(
      new ApiError('conflict', 409, { detail: 'Cannot delete a category that is still used' }),
    );

    render(<ProductCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByText('Fasteners')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete fasteners/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/still used/i);
    expect(screen.getByText('Fasteners')).toBeInTheDocument();
  });

  it('deletes an unused category and refreshes the list', async () => {
    mockedListProductCategories.mockResolvedValueOnce({
      items: [fasteners],
      total: 1,
      limit: 50,
      offset: 0,
    });
    mockedDeleteProductCategory.mockResolvedValue(undefined);
    mockedListProductCategories.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    render(<ProductCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByText('Fasteners')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete fasteners/i }));

    await waitFor(() => {
      expect(screen.queryByText('Fasteners')).not.toBeInTheDocument();
    });
  });
});
