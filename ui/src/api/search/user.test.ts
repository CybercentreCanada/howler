import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/search/user'));

vi.mock('api', () => ({
  hpost: mockHpost,
  joinUri: mockJoinUri
}));

vi.mock('api/search', () => ({
  uri: () => '/api/v1/search'
}));

import { post, uri } from './user';

describe('search user API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the user search endpoint URI', () => {
    expect(uri()).toBe('/api/v1/search/user');
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1/search', 'user');
  });

  it('defaults the query and maps uname to username', async () => {
    mockHpost.mockResolvedValue({
      items: [{ uname: 'alice', display_name: 'Alice' }],
      total: 1
    });

    await expect(post()).resolves.toEqual({
      items: [{ uname: 'alice', display_name: 'Alice', username: 'alice' }],
      total: 1
    });
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/search/user', { query: 'name:*' });
  });

  it('preserves the provided request while ensuring a default query exists', async () => {
    mockHpost.mockResolvedValue({ items: [], total: 0 });

    await post({ rows: 10, query: 'name:demo' } as any);

    expect(mockHpost).toHaveBeenCalledWith('/api/v1/search/user', { rows: 10, query: 'name:demo' });
  });

  it('throws when the search response is empty', async () => {
    mockHpost.mockResolvedValue(undefined);

    await expect(post({ query: 'name:test' } as any)).rejects.toThrow('Search response was empty.');
  });
});
