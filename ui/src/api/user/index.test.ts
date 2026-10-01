import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hget: mockHget,
  hput: mockHput,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('api/user/avatar', () => ({ sentinel: 'avatar' }));
vi.mock('api/user/groups', () => ({ sentinel: 'groups' }));
vi.mock('api/user/whoami', () => ({ sentinel: 'whoami' }));

import { avatar, get, groups, put, uri, whoami } from './index';

describe('user API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockHput.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail user URIs', () => {
    expect(uri()).toBe('/api/v1/user');
    expect(uri('alice')).toBe('/api/v1/user/alice');
  });

  it('gets and updates a user with optional refresh params', async () => {
    const refresh = new URLSearchParams({ refresh: 'false' });

    await get('alice');
    await put('alice', { display_name: 'Alice' } as any, 'false');

    expect(mockHget).toHaveBeenCalledWith('/api/v1/user/alice');
    expect(mockHput).toHaveBeenCalledWith('/api/v1/user/alice', { display_name: 'Alice' }, undefined, refresh);
  });

  it('re-exports nested user modules', () => {
    expect(avatar).toEqual({ sentinel: 'avatar' });
    expect(groups).toEqual({ sentinel: 'groups' });
    expect(whoami).toEqual({ sentinel: 'whoami' });
  });
});
