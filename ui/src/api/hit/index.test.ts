import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/hit'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('api/hit/assign', () => ({ sentinel: 'assign' }));
vi.mock('api/hit/comments', () => ({ sentinel: 'comments' }));
vi.mock('api/hit/labels', () => ({ sentinel: 'labels' }));
vi.mock('api/hit/overwrite', () => ({ sentinel: 'overwrite' }));
vi.mock('api/hit/transition', () => ({ sentinel: 'transition' }));

import { assign, comments, del, get, labels, overwrite, post, transition, uri } from './index';

describe('hit API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds hit URIs', () => {
    expect(uri()).toBe('/api/v1/hit');
    expect(uri('abc')).toBe('/api/v1/hit/abc');
  });

  it('gets hits with metadata and sends bulk write operations with refresh params', async () => {
    const refresh = new URLSearchParams({ refresh: 'true' });
    await get('abc', ['one', 'two']);
    await post([{ id: '1' }] as any, 'true');
    await del(['1', '2'], 'true');

    expect(mockHget).toHaveBeenCalledWith('/api/v1/hit/abc', new URLSearchParams({ metadata: 'one,two' }));
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/hit', [{ id: '1' }], undefined, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/hit', ['1', '2'], undefined, refresh);
  });

  it('re-exports nested hit modules', () => {
    expect(assign).toEqual({ sentinel: 'assign' });
    expect(comments).toEqual({ sentinel: 'comments' });
    expect(labels).toEqual({ sentinel: 'labels' });
    expect(overwrite).toEqual({ sentinel: 'overwrite' });
    expect(transition).toEqual({ sentinel: 'transition' });
  });
});
