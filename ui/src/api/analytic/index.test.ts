import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/analytic'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('api/analytic/comments', () => ({ sentinel: 'comments' }));
vi.mock('api/analytic/favourite', () => ({ sentinel: 'favourite' }));
vi.mock('api/analytic/notebooks', () => ({ sentinel: 'notebooks' }));
vi.mock('api/analytic/owner', () => ({ sentinel: 'owner' }));

import { comments, del, favourite, get, notebooks, owner, put, uri } from './index';

describe('analytic API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds list and detail URIs', () => {
    expect(uri()).toBe('/api/v1/analytic');
    expect(uri('abc')).toBe('/api/v1/analytic/abc');
  });

  it('gets one analytic or the collection', async () => {
    mockHget.mockResolvedValueOnce([{ id: '1' }]).mockResolvedValueOnce({ id: '2' });

    await expect(get()).resolves.toEqual([{ id: '1' }]);
    await expect(get('2')).resolves.toEqual({ id: '2' });
    expect(mockHget).toHaveBeenNthCalledWith(1, '/api/v1/analytic');
    expect(mockHget).toHaveBeenNthCalledWith(2, '/api/v1/analytic/2');
  });

  it('updates and deletes analytics with optional refresh params', async () => {
    const refresh = new URLSearchParams({ refresh: 'wait_for' });
    mockHput.mockResolvedValue({ id: '2' });
    mockHdelete.mockResolvedValue(undefined);

    await put('2', { description: 'updated' } as any, 'wait_for');
    await del('2', 'wait_for');

    expect(mockHput).toHaveBeenCalledWith('/api/v1/analytic/2', { description: 'updated' }, undefined, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/analytic/2', undefined, undefined, refresh);
  });

  it('re-exports related analytic API modules', () => {
    expect(comments).toEqual({ sentinel: 'comments' });
    expect(favourite).toEqual({ sentinel: 'favourite' });
    expect(notebooks).toEqual({ sentinel: 'notebooks' });
    expect(owner).toEqual({ sentinel: 'owner' });
  });
});
