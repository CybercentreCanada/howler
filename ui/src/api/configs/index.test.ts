import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/configs'));

vi.mock('api', () => ({
  hget: mockHget,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

import { get, uri } from './index';

describe('configs API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the configs URI and fetches configs', async () => {
    mockHget.mockResolvedValue({ indexes: {} });
    expect(uri()).toBe('/api/v1/configs');
    await expect(get()).resolves.toEqual({ indexes: {} });
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1', 'configs');
    expect(mockHget).toHaveBeenCalledWith('/api/v1/configs');
  });
});
