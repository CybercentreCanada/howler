import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hpost: mockHpost,
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/v2', () => ({
  uri: () => '/api/v2'
}));

vi.mock('./facet', () => ({
  facet: { sentinel: true }
}));

import { facet, post, uri } from './index';

describe('v2 search API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds the v2 multi-index search URI', () => {
    expect(uri(['hit', 'event'])).toBe('/api/v2/search/hit,event');
    expect(mockJoinAllUri).toHaveBeenCalledWith('/api/v2', 'search', 'hit,event');
  });

  it('posts a search request for a single index string', async () => {
    mockHpost.mockResolvedValue({ items: [], total: 0 });

    await post('hit', { rows: 25 } as any);

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/search/hit', { rows: 25, query: 'howler.id:*' });
  });

  it('preserves a provided query for multiple indexes', async () => {
    mockHpost.mockResolvedValue({ items: [], total: 0 });

    await post(['hit', 'case'], { query: 'status:open' } as any);

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/search/hit,case', { query: 'status:open' });
  });

  it('rejects nullish, invalid, or empty indexes', async () => {
    expect(() => post(undefined as any, {} as any)).toThrow('Indexes cannot be null or undefined.');
    expect(() => post('hit,invalid', {} as any)).toThrow('Only hit, case, and event indexes should be used currently.');
    expect(() => post('', {} as any)).toThrow('indexes must have length of at least 1.');
  });

  it('re-exports the facet module', () => {
    expect((facet as any).facet).toEqual({ sentinel: true });
  });
});
