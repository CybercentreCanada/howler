import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hpost: mockHpost,
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/hit', () => ({
  uri: () => '/api/v1/hit'
}));

import { post, uri } from './transition';

describe('hit transition API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds the transition URI and posts the transition body', async () => {
    const refresh = new URLSearchParams({ refresh: 'false' });
    const body = { transition: 'resolve', data: { reason: 'done' } };

    expect(uri('id-1')).toBe('/api/v1/hit/id-1/transition');
    await post('id-1', body, 'false');

    expect(mockHpost).toHaveBeenCalledWith('/api/v1/hit/id-1/transition', body, undefined, refresh);
  });
});
