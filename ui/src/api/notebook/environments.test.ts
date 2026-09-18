import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hget: mockHget,
  joinUri: mockJoinUri
}));

vi.mock('api/notebook', () => ({
  uri: () => '/api/v1/notebook'
}));

import { get, uri } from './environments';

describe('notebook environments API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the environments URI and performs the GET request', async () => {
    expect(uri()).toBe('/api/v1/notebook/environments');
    await get();
    expect(mockHget).toHaveBeenCalledWith('/api/v1/notebook/environments');
  });
});
