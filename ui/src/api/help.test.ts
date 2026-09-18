import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1'));

vi.mock('api', () => ({
  hget: mockHget,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

import { get, uri } from './help';

describe('help API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the help endpoint URI from the API root', () => {
    expect(uri()).toBe('/api/v1');
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1', '');
  });

  it('fetches the help payload from the help endpoint', async () => {
    const payload = { apis: [], blueprints: {} };
    mockHget.mockResolvedValue(payload);

    await expect(get()).resolves.toEqual(payload);
    expect(mockHget).toHaveBeenCalledWith('/api/v1');
  });
});
