import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockCreatePermissionsApi = vi.hoisted(() => vi.fn(() => ({ canEdit: vi.fn() })));
const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/dossier'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('api/utils/createPermissionsApi', () => ({
  default: mockCreatePermissionsApi
}));

vi.mock('./groups', () => ({
  sentinel: 'groups'
}));

import { del, get, groups, permission, post, put, uri } from './index';

describe('dossier API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail URIs', () => {
    expect(uri()).toBe('/api/v1/dossier');
    expect(uri('abc')).toBe('/api/v1/dossier/abc');
  });

  it('fetches either one dossier or the dossier collection', async () => {
    mockHget.mockResolvedValueOnce([{ id: 'one' }]).mockResolvedValueOnce({ id: 'two' });

    await expect(get()).resolves.toEqual([{ id: 'one' }]);
    await expect(get('two')).resolves.toEqual({ id: 'two' });
  });

  it('posts, puts, and deletes dossiers with refresh params', async () => {
    const refresh = new URLSearchParams({ refresh: 'true' });

    await post({ title: 'new' } as any, 'true');
    await put('id-1', { title: 'updated' } as any, 'true');
    await del('id-1', 'true');

    expect(mockHpost).toHaveBeenCalledWith('/api/v1/dossier', { title: 'new' }, undefined, refresh);
    expect(mockHput).toHaveBeenCalledWith('/api/v1/dossier/id-1', { title: 'updated' }, undefined, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/dossier/id-1', undefined, undefined, refresh);
  });

  it('creates the permission helper from the dossier URI and re-exports groups', () => {
    expect(mockCreatePermissionsApi).toHaveBeenCalledWith(uri);
    expect(permission).toEqual({ canEdit: expect.any(Function) });
    expect(groups).toEqual({ sentinel: 'groups' });
  });
});
