/**
 * Loops a paginated fetcher (any module's `list*` API function) until every item
 * has been retrieved, instead of a caller silently rendering only the first page
 * (e.g. the first 200 of 250 categories in a filter dropdown) with no indication
 * anything was left out. Intended for bounded "option list" data (categories,
 * tags, people, document versions/acknowledgements for one document) where a
 * complete in-memory list is the right shape for the UI, not a paginated table.
 */
export async function fetchAllPages<T>(
  fetchPage: (params: { limit: number; offset: number }) => Promise<{ items: T[]; total: number }>,
  { pageSize = 200 }: { pageSize?: number } = {},
): Promise<T[]> {
  const results: T[] = [];
  let offset = 0;
  for (;;) {
    const page = await fetchPage({ limit: pageSize, offset });
    results.push(...page.items);
    offset += page.items.length;
    if (page.items.length === 0 || offset >= page.total) {
      break;
    }
  }
  return results;
}
