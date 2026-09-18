import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hput: mockHput,
  joinAllUri: mockJoinAllUri
}));

import createPermissionsApi from './createPermissionsApi';

describe('createPermissionsApi', () => {
  const parentUri = (id: string) => `/api/v1/example/${id}`;

  beforeEach(() => {
    mockHdelete.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('builds permission routes relative to the parent URI', async () => {
    const permissionApi = createPermissionsApi(parentUri);
    const payload = { privilege: 'W', user_ids: ['1', '2'] };

    await permissionApi.put('abc', payload);
    await permissionApi.delete('abc', payload);

    expect(mockJoinAllUri).toHaveBeenCalledWith('/api/v1/example/abc', 'permission');
    expect(mockHput).toHaveBeenCalledWith('/api/v1/example/abc/permission', payload);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/example/abc/permission', payload);
  });
});
