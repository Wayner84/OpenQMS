import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../shared/api/client';
import {
  createCategory,
  createTag,
  deleteCategory,
  deleteTag,
  listCategories,
  listTags,
  updateCategory,
} from './api';
import { DocumentCategoriesPage } from './DocumentCategoriesPage';

vi.mock('./api');

const mockedListCategories = vi.mocked(listCategories);
const mockedListTags = vi.mocked(listTags);
const mockedCreateCategory = vi.mocked(createCategory);
const mockedUpdateCategory = vi.mocked(updateCategory);
const mockedDeleteCategory = vi.mocked(deleteCategory);
const mockedCreateTag = vi.mocked(createTag);
const mockedDeleteTag = vi.mocked(deleteTag);

const qualityCategory = {
  id: 'c1',
  organisation_id: 'o1',
  name: 'Quality',
  parent_category_id: null,
};
const controlledTag = { id: 't1', organisation_id: 'o1', name: 'controlled' };

/** A promise plus its resolvers, for tests that need precise control over when a
 * mocked API call settles -- used to prove an out-of-order (slower, earlier)
 * `loadAll` refresh can't overwrite state a later, faster refresh already set. */
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

describe('DocumentCategoriesPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows a loading state, then the categories and tags', async () => {
    mockedListCategories.mockResolvedValue({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [controlledTag], total: 1, limit: 200, offset: 0 });

    render(<DocumentCategoriesPage />);

    expect(screen.getByRole('status')).toBeInTheDocument();
    // `getByRole('cell', ...)`, not `getByText`: "Quality" also appears as an
    // `<option>` in the "Parent category" select once any category exists, which
    // `getByText` would match too and make the query ambiguous.
    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    });
    expect(screen.getByText('controlled')).toBeInTheDocument();
  });

  it('loads under React StrictMode (dev-mode double-invokes effects on mount)', async () => {
    mockedListCategories.mockResolvedValue({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    render(
      <StrictMode>
        <DocumentCategoriesPage />
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    });
  });

  it('shows an error message when loading fails', async () => {
    mockedListCategories.mockRejectedValue(new Error('network error'));
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    render(<DocumentCategoriesPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not load categories and tags/i,
    );
  });

  it('creates a category and refreshes the list', async () => {
    mockedListCategories.mockResolvedValueOnce({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedCreateCategory.mockResolvedValue(qualityCategory);
    mockedListCategories.mockResolvedValueOnce({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });

    render(<DocumentCategoriesPage />);
    await waitFor(() => {
      expect(mockedListCategories).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/category name/i), { target: { value: 'Quality' } });
    fireEvent.click(screen.getByRole('button', { name: /^create category$/i }));

    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    });
    expect(mockedCreateCategory).toHaveBeenCalledWith({
      name: 'Quality',
      parent_category_id: undefined,
    });
  });

  it('edits a category', async () => {
    mockedListCategories.mockResolvedValueOnce({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedUpdateCategory.mockResolvedValue({ ...qualityCategory, name: 'Quality Assurance' });
    mockedListCategories.mockResolvedValueOnce({
      items: [{ ...qualityCategory, name: 'Quality Assurance' }],
      total: 1,
      limit: 200,
      offset: 0,
    });

    render(<DocumentCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit quality/i }));
    fireEvent.change(screen.getByLabelText(/category name/i), {
      target: { value: 'Quality Assurance' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality Assurance' })).toBeInTheDocument();
    });
    expect(mockedUpdateCategory).toHaveBeenCalledWith(
      'c1',
      expect.objectContaining({ name: 'Quality Assurance' }),
    );
  });

  it('excludes a category itself and its descendants from its own "parent" choices while editing', async () => {
    // A (c1) -> B (c2) -> C (c3). Editing A must not offer A, B, or C as its own
    // parent -- self and direct-child exclusion alone would still let A be
    // reparented under its grandchild C, creating a cycle the backend would
    // reject with a 422 (see the equivalent backend test in
    // test_documents_service.py), but a round trip for a choice that can never
    // succeed is worth avoiding client-side too.
    const categoryA = qualityCategory;
    const categoryB = { id: 'c2', organisation_id: 'o1', name: 'B', parent_category_id: 'c1' };
    const categoryC = { id: 'c3', organisation_id: 'o1', name: 'C', parent_category_id: 'c2' };
    const categoryD = { id: 'c4', organisation_id: 'o1', name: 'D', parent_category_id: null };
    mockedListCategories.mockResolvedValue({
      items: [categoryA, categoryB, categoryC, categoryD],
      total: 4,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    render(<DocumentCategoriesPage />);
    // Not `getByRole('cell', { name: 'Quality' })` here: with this deeper
    // hierarchy, "Quality" is now also B's displayed parent name, in a second
    // cell, making that query ambiguous. The "Edit Quality" button text is
    // unambiguous (no other category is named exactly "Quality") and is what
    // this test needs anyway.
    const editButton = await screen.findByRole('button', { name: /^edit quality$/i });

    fireEvent.click(editButton);

    const parentSelect = screen.getByLabelText(/parent category/i);
    const optionLabels = Array.from(parentSelect.querySelectorAll('option')).map(
      (option) => option.textContent,
    );
    expect(optionLabels).not.toContain('Quality');
    expect(optionLabels).not.toContain('B');
    expect(optionLabels).not.toContain('C');
    expect(optionLabels).toContain('D');
  });

  it('shows the server conflict message when deleting a category that is still in use', async () => {
    mockedListCategories.mockResolvedValue({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedDeleteCategory.mockRejectedValue(
      new ApiError('conflict', 409, {
        detail: 'Cannot delete a category that is still referenced',
      }),
    );
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<DocumentCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete quality/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/still referenced/i);
  });

  it('asks for confirmation before deleting a category, and does not delete when declined', async () => {
    mockedListCategories.mockResolvedValue({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedListTags.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<DocumentCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete quality/i }));

    await Promise.resolve();
    expect(confirmSpy).toHaveBeenCalled();
    expect(mockedDeleteCategory).not.toHaveBeenCalled();
  });

  it('creates a tag and refreshes the list', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValueOnce({ items: [], total: 0, limit: 200, offset: 0 });
    mockedCreateTag.mockResolvedValue(controlledTag);
    mockedListTags.mockResolvedValueOnce({
      items: [controlledTag],
      total: 1,
      limit: 200,
      offset: 0,
    });

    render(<DocumentCategoriesPage />);
    await waitFor(() => {
      expect(mockedListTags).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/tag name/i), { target: { value: 'controlled' } });
    fireEvent.click(screen.getByRole('button', { name: /^create tag$/i }));

    await waitFor(() => {
      expect(screen.getByText('controlled')).toBeInTheDocument();
    });
    expect(mockedCreateTag).toHaveBeenCalledWith({ name: 'controlled' });
  });

  it('deletes a tag', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValueOnce({
      items: [controlledTag],
      total: 1,
      limit: 200,
      offset: 0,
    });
    mockedDeleteTag.mockResolvedValue(undefined);
    mockedListTags.mockResolvedValueOnce({ items: [], total: 0, limit: 200, offset: 0 });
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<DocumentCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByText('controlled')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete controlled/i }));

    await waitFor(() => {
      expect(screen.queryByText('controlled')).not.toBeInTheDocument();
    });
    expect(mockedDeleteTag).toHaveBeenCalledWith('t1');
  });

  it('does not let a stale, out-of-order loadAll response (StrictMode double-invoke) overwrite a fresher one', async () => {
    // React 18 StrictMode double-invokes the mount effect (mount, cleanup, mount
    // again) synchronously, so both `loadAll` calls dispatch their requests before
    // either resolves -- exactly the shape of a real out-of-order-response race,
    // and reproducible without any real network timing.
    const staleCategories = deferred<{
      items: (typeof qualityCategory)[];
      total: number;
      limit: number;
      offset: number;
    }>();
    mockedListCategories.mockReturnValueOnce(staleCategories.promise);
    mockedListCategories.mockResolvedValueOnce({
      items: [qualityCategory],
      total: 1,
      limit: 200,
      offset: 0,
    });
    const staleTags = deferred<{
      items: (typeof controlledTag)[];
      total: number;
      limit: number;
      offset: number;
    }>();
    mockedListTags.mockReturnValueOnce(staleTags.promise);
    mockedListTags.mockResolvedValueOnce({
      items: [controlledTag],
      total: 1,
      limit: 200,
      offset: 0,
    });

    render(
      <StrictMode>
        <DocumentCategoriesPage />
      </StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    });
    expect(screen.getByText('controlled')).toBeInTheDocument();

    // The first (StrictMode-simulated, discarded) invocation's response finally
    // arrives, empty -- it must not overwrite the second invocation's data, which
    // is already showing.
    staleCategories.resolve({ items: [], total: 0, limit: 200, offset: 0 });
    staleTags.resolve({ items: [], total: 0, limit: 200, offset: 0 });
    await new Promise((resolve) => {
      setTimeout(resolve, 0);
    });

    expect(screen.getByRole('cell', { name: 'Quality' })).toBeInTheDocument();
    expect(screen.getByText('controlled')).toBeInTheDocument();
  });

  it('asks for confirmation before deleting a tag, and does not delete when declined', async () => {
    mockedListCategories.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    mockedListTags.mockResolvedValue({
      items: [controlledTag],
      total: 1,
      limit: 200,
      offset: 0,
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<DocumentCategoriesPage />);
    await waitFor(() => {
      expect(screen.getByText('controlled')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete controlled/i }));

    await Promise.resolve();
    expect(confirmSpy).toHaveBeenCalled();
    expect(mockedDeleteTag).not.toHaveBeenCalled();
  });
});
