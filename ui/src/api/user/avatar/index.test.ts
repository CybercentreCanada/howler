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

import { get, uri } from './index';

describe('user avatar API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the avatar URI and performs the GET request', async () => {
    expect(uri('alice')).toBe('/api/v1/user/avatar/alice');
    await get('alice');
    expect(mockHget).toHaveBeenCalledWith('/api/v1/user/avatar/alice');
  });
});
