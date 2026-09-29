import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockCreatePermissionsApi = vi.hoisted(() => vi.fn(() => ({ put: vi.fn(), delete: vi.fn() })));
const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/view'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('../utils/createPermissionsApi', () => ({
  default: mockCreatePermissionsApi
}));

vi.mock('api/view/favourite', () => ({
  sentinel: 'favourite'
}));

import { del, favourite, get, permission, post, put, uri } from './index';

describe('view API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail view URIs', () => {
    expect(uri()).toBe('/api/v1/view');
    expect(uri('view-1')).toBe('/api/v1/view/view-1');
  });

  it('gets, creates, updates, and deletes views', async () => {
    const refresh = new URLSearchParams({ refresh: 'wait_for' });

    await get();
    await post({ title: 'new' } as any, 'wait_for');
    await put('view-1', { title: 'updated' } as any, 'wait_for');
    await del('view-1', 'wait_for');

    expect(mockHget).toHaveBeenCalledWith('/api/v1/view');
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/view', { title: 'new' }, undefined, refresh);
    expect(mockHput).toHaveBeenCalledWith('/api/v1/view/view-1', { title: 'updated' }, undefined, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/view/view-1', undefined, undefined, refresh);
  });

  it('creates permission helpers and re-exports favourites', () => {
    expect(mockCreatePermissionsApi).toHaveBeenCalledWith(uri);
    expect(permission).toEqual({ put: expect.any(Function), delete: expect.any(Function) });
    expect(favourite).toEqual({ sentinel: 'favourite' });
  });
});
