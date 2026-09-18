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

import { post, uri } from './fuzzy';

describe('v2 fuzzy API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds the fuzzy endpoint URI', () => {
    expect(uri()).toBe('/api/v2/fuzzy');
    expect(mockJoinAllUri).toHaveBeenCalledWith('/api/v2', 'fuzzy');
  });

  it('posts a fuzzy search request to the nested search endpoint', async () => {
    mockHpost.mockResolvedValue({ items: [], total: 0 });

    await post({ query: 'hello world', indexes: ['hit'] });

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/fuzzy/search', { query: 'hello world', indexes: ['hit'] });
  });

  it('rejects blank fuzzy search queries', () => {
    expect(() => post({ query: '   ' })).toThrow('Search query is required.');
    expect(() => post({ query: '' })).toThrow('Search query is required.');
  });
});
