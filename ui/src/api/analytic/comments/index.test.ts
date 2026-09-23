import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri
}));

vi.mock('api/analytic', () => ({
  uri: (analytic: string) => `/api/v1/analytic/${analytic}`
}));

vi.mock('./react', () => ({ sentinel: 'react-comments' }));

import { del, get, post, put, react, uri } from './index';

describe('analytic comments API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail URIs, performs CRUD operations, and re-exports reactions', async () => {
    expect(uri('an-1')).toBe('/api/v1/analytic/an-1/comments');
    expect(uri('an-1', 'c-1')).toBe('/api/v1/analytic/an-1/comments/c-1');

    await get('an-1', 'c-1');
    await put('an-1', 'c-1', 'edited');
    await post('an-1', 'value', 'det-1');
    await del('an-1', ['c-1']);

    expect(mockHget).toHaveBeenCalledWith('/api/v1/analytic/an-1/comments/c-1');
    expect(mockHput).toHaveBeenCalledWith('/api/v1/analytic/an-1/comments/c-1', { value: 'edited' });
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/analytic/an-1/comments', { value: 'value', detection: 'det-1' });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/analytic/an-1/comments', ['c-1']);
    expect(react).toEqual({ sentinel: 'react-comments' });
  });
});
