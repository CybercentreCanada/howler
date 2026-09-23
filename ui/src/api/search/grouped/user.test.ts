import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hpost: mockHpost,
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/search/grouped', () => ({
  uri: () => '/api/v1/search/grouped'
}));

import { post, uri } from './user';

describe('grouped user search API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds grouped user URIs, applies a default query, and maps uname to username', async () => {
    mockHpost.mockResolvedValueOnce({
      items: [{ items: [{ uname: 'alice', display_name: 'Alice' }] }],
      total: 1
    });

    expect(uri('owner')).toBe('/api/v1/search/grouped/user/owner');
    await expect(post('owner')).resolves.toEqual({
      items: [{ items: [{ uname: 'alice', display_name: 'Alice', username: 'alice' }] }],
      total: 1
    });
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/search/grouped/user/owner', { query: 'uname:*' });
  });

  it('throws when the grouped response is empty', async () => {
    mockHpost.mockResolvedValueOnce(undefined);
    await expect(post('owner', { query: 'uname:alice' } as any)).rejects.toThrow('Grouped search response was empty.');
  });
});
