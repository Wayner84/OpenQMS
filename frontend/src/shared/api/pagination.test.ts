import { describe, expect, it, vi } from 'vitest';

import { fetchAllPages } from './pagination';

interface Item {
  id: string;
}

describe('fetchAllPages', () => {
  it('returns every item after a single page when total fits in one page', async () => {
    const fetchPage = vi.fn().mockResolvedValue({
      items: [{ id: '1' }, { id: '2' }],
      total: 2,
    });

    const result = await fetchAllPages<Item>(fetchPage);

    expect(result).toEqual([{ id: '1' }, { id: '2' }]);
    expect(fetchPage).toHaveBeenCalledTimes(1);
    expect(fetchPage).toHaveBeenCalledWith({ limit: 200, offset: 0 });
  });

  it('keeps requesting subsequent pages until the reported total is reached', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ items: [{ id: '1' }, { id: '2' }], total: 5 })
      .mockResolvedValueOnce({ items: [{ id: '3' }, { id: '4' }], total: 5 })
      .mockResolvedValueOnce({ items: [{ id: '5' }], total: 5 });

    const result = await fetchAllPages<Item>(fetchPage, { pageSize: 2 });

    expect(result).toEqual([{ id: '1' }, { id: '2' }, { id: '3' }, { id: '4' }, { id: '5' }]);
    expect(fetchPage).toHaveBeenCalledTimes(3);
    expect(fetchPage).toHaveBeenNthCalledWith(1, { limit: 2, offset: 0 });
    expect(fetchPage).toHaveBeenNthCalledWith(2, { limit: 2, offset: 2 });
    expect(fetchPage).toHaveBeenNthCalledWith(3, { limit: 2, offset: 4 });
  });

  it('returns an empty array without ever calling the fetcher twice when the first page is empty', async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [], total: 0 });

    const result = await fetchAllPages<Item>(fetchPage);

    expect(result).toEqual([]);
    expect(fetchPage).toHaveBeenCalledTimes(1);
  });

  it('does not silently truncate option lists at a fixed item cap', async () => {
    const fetchPage = vi.fn(({ offset }: { limit: number; offset: number }) =>
      Promise.resolve({ items: [{ id: String(offset + 1) }], total: 2_001 }),
    );

    const result = await fetchAllPages<Item>(fetchPage, { pageSize: 1 });

    expect(result).toHaveLength(2_001);
    expect(result.at(-1)).toEqual({ id: '2001' });
    expect(fetchPage).toHaveBeenCalledTimes(2_001);
  });
});
