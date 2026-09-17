import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());

vi.mock('api', async () => {
  const urlJoin = (await import('url-join')).default;
  return {
    hget: mockHget,
    joinAllUri: (...parts: string[]) => urlJoin(...parts)
  };
});

vi.mock('api/dossier', () => ({
  uri: () => '/api/v1/dossier'
}));

import { get, uri } from './groups';

describe('dossier groups API', () => {
  beforeEach(() => {
    mockHget.mockReset();
  });

  it('builds the groups endpoint URI', () => {
    expect(uri()).toBe('/api/v1/dossier/groups');
  });

  it('requests groups with the prefix query parameter', async () => {
    mockHget.mockResolvedValue(['network/dns']);

    await expect(get('network')).resolves.toEqual(['network/dns']);
    expect(mockHget).toHaveBeenCalledWith('/api/v1/dossier/groups', new URLSearchParams({ prefix: 'network' }));
  });
});
