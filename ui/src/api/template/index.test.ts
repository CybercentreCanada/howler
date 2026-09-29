import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/template'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

import { del, get, post, put, uri } from './index';

describe('template API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail template URIs', () => {
    expect(uri()).toBe('/api/v1/template');
    expect(uri('template-1')).toBe('/api/v1/template/template-1');
  });

  it('gets templates with an empty fallback and performs write operations', async () => {
    const refresh = new URLSearchParams({ refresh: 'false' });
    mockHget.mockResolvedValueOnce(undefined).mockResolvedValueOnce([{ id: 'template-1' }]);

    await expect(get()).resolves.toEqual([]);
    await expect(get()).resolves.toEqual([{ id: 'template-1' }]);
    await post({ title: 'new' } as any, 'false');
    await put('template-1', ['field'], 'false');
    await del('template-1', 'false');

    expect(mockHpost).toHaveBeenCalledWith('/api/v1/template', { title: 'new' }, undefined, refresh);
    expect(mockHput).toHaveBeenCalledWith('/api/v1/template/template-1', ['field'], undefined, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/template/template-1', undefined, undefined, refresh);
  });
});
