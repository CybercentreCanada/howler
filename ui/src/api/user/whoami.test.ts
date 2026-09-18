import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/user/whoami'));

vi.mock('api', () => ({
  hget: mockHget,
  joinUri: mockJoinUri
}));

vi.mock('api/user', () => ({
  uri: () => '/api/v1/user'
}));

import { get, uri } from './whoami';

describe('user whoami API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the whoami URI', () => {
    expect(uri()).toBe('/api/v1/user/whoami');
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1/user', 'whoami');
  });

  it('fetches the current user', async () => {
    mockHget.mockResolvedValue({ username: 'me' });
    await expect(get()).resolves.toEqual({ username: 'me' });
    expect(mockHget).toHaveBeenCalledWith('/api/v1/user/whoami');
  });
});
