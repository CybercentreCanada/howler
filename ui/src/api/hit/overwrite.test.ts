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

import { put, uri } from './overwrite';

describe('hit overwrite API', () => {
  beforeEach(() => {
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds the overwrite URI and forwards the overwrite body', async () => {
    const refresh = new URLSearchParams({ refresh: 'true' });

    expect(uri('id-1')).toBe('/api/v1/hit/id-1/overwrite');
    await put('id-1', { status: 'open' } as any, 'true');

    expect(mockHput).toHaveBeenCalledWith('/api/v1/hit/id-1/overwrite', { status: 'open' }, undefined, refresh);
  });
});
