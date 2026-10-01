import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hget: mockHget,
  joinUri: mockJoinUri
}));

vi.mock('api/user', () => ({
  uri: () => '/api/v1/user'
}));

import { get, uri } from './groups';

describe('user groups API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the groups URI and performs the GET request', async () => {
    expect(uri()).toBe('/api/v1/user/groups');
    await get();
    expect(mockHget).toHaveBeenCalledWith('/api/v1/user/groups');
  });
});
