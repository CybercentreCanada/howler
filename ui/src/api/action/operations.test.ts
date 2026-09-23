import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/action/operations'));

vi.mock('api', () => ({
  hget: mockHget,
  joinUri: mockJoinUri
}));

vi.mock('api/action', () => ({
  uri: () => '/api/v1/action'
}));

import { get, uri } from './operations';

describe('action operations API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the operations URI and returns an empty fallback', async () => {
    mockHget.mockResolvedValueOnce(undefined).mockResolvedValueOnce([{ id: 'add_label' }]);

    expect(uri()).toBe('/api/v1/action/operations');
    await expect(get()).resolves.toEqual([]);
    await expect(get()).resolves.toEqual([{ id: 'add_label' }]);
  });
});
