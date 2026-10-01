import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hput: mockHput,
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/hit', () => ({
  uri: () => '/api/v1/hit'
}));

import { del, put, uri } from './labels';

describe('hit labels API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds the label URI and performs add/remove operations', async () => {
    const refresh = new URLSearchParams({ refresh: 'wait_for' });
    const body = { value: ['x'] };

    expect(uri('id-1', 'insight')).toBe('/api/v1/hit/id-1/labels/insight');
    await put('id-1', 'insight', body, 'wait_for');
    await del('id-1', 'insight', body, 'wait_for');

    expect(mockHput).toHaveBeenCalledWith('/api/v1/hit/id-1/labels/insight', body, undefined, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/hit/id-1/labels/insight', body, undefined, refresh);
  });
});
