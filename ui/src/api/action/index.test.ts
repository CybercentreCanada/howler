import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockCreatePermissionsApi = vi.hoisted(() => vi.fn(() => ({ put: vi.fn(), delete: vi.fn() })));
const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpatch = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/action'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpatch: mockHpatch,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('../utils/createPermissionsApi', () => ({
  default: mockCreatePermissionsApi
}));

vi.mock('api/action/execute', () => ({ sentinel: 'execute' }));
vi.mock('api/action/operations', () => ({ sentinel: 'operations' }));

import { del, execute, get, operations, patch, permission, post, put, uri } from './index';

describe('action API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpatch.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds list and detail URIs', () => {
    expect(uri()).toBe('/api/v1/action');
    expect(uri('abc')).toBe('/api/v1/action/abc');
  });

  it('gets, creates, updates, patches, and deletes actions', async () => {
    const refresh = new URLSearchParams({ refresh: 'wait_for' });
    await get('id-1');
    await post({ id: 'new' } as any, 'wait_for');
    await put('id-2', { id: 'updated' } as any, 'wait_for');
    await patch('id-3', { id: 'patched' } as any, 'wait_for');
    await del('id-4', 'wait_for');

    expect(mockHget).toHaveBeenCalledWith('/api/v1/action/id-1');
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/action', { id: 'new' }, {}, refresh);
    expect(mockHput).toHaveBeenCalledWith('/api/v1/action/id-2', { id: 'updated' }, {}, refresh);
    expect(mockHpatch).toHaveBeenCalledWith('/api/v1/action/id-3', { id: 'patched' }, {}, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/action/id-4', undefined, undefined, refresh);
  });

  it('creates permission helpers and re-exports nested action modules', () => {
    expect(mockCreatePermissionsApi).toHaveBeenCalledWith(uri);
    expect(permission).toEqual({ put: expect.any(Function), delete: expect.any(Function) });
    expect(execute).toEqual({ sentinel: 'execute' });
    expect(operations).toEqual({ sentinel: 'operations' });
  });
});
