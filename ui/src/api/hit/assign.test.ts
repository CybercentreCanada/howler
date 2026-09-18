import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hput: mockHput,
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/hit', () => ({
  uri: () => '/api/v1/hit'
}));

import { put, uri } from './assign';

describe('hit assign API', () => {
  beforeEach(() => {
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds the assign URI and performs the PUT request', async () => {
    expect(uri('hit-1')).toBe('/api/v1/hit/hit-1/assign');
    await put('hit-1', { value: 'demo' });
    expect(mockHput).toHaveBeenCalledWith('/api/v1/hit/hit-1/assign', { value: 'demo' });
  });
});
