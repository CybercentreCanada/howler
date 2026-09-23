import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hpost: mockHpost,
  hput: mockHput,
  joinUri: mockJoinUri
}));

vi.mock('api/v2/case', () => ({
  uri: (id: string) => `/api/v2/case/${id}`
}));

import { del, post, put, uri } from './items';

describe('v2 case items API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the items URI and performs create, delete, and update operations', async () => {
    expect(uri('case-1')).toBe('/api/v2/case/case-1/items');

    await post('case-1', { id: 'item-1', name: 'Item' } as any);
    await del('case-1', 'item-1');
    await del('case-1', ['item-1', 'item-2'], true);
    await put('case-1', 'item-3', { name: 'Updated' });

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/case/case-1/items', { id: 'item-1', name: 'Item' });
    expect(mockHdelete).toHaveBeenNthCalledWith(1, '/api/v2/case/case-1/items', { ids: ['item-1'], force: false });
    expect(mockHdelete).toHaveBeenNthCalledWith(2, '/api/v2/case/case-1/items', { ids: ['item-1', 'item-2'], force: true });
    expect(mockHput).toHaveBeenCalledWith('/api/v2/case/case-1/items', { id: 'item-3', name: 'Updated' });
  });
});
