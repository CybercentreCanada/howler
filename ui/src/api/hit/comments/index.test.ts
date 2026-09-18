import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn((_base: string, _part: string) => '/api/v1/hit/hit-1/comments'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri
}));

vi.mock('api/hit', () => ({
  uri: (id: string) => `/api/v1/hit/${id}`
}));

vi.mock('./react', () => ({
  sentinel: 'react'
}));

import { del, get, post, put, react, uri } from './index';

describe('hit comments API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds list and detail comment URIs', () => {
    expect(uri('hit-1')).toBe('/api/v1/hit/hit-1/comments');
    expect(uri('hit-1', 'comment-1')).toBe('/api/v1/hit/hit-1/comments/comment-1');
  });

  it('gets, creates, updates, and deletes hit comments', async () => {
    await get('hit-1', 'comment-1');
    await put('hit-1', 'comment-1', 'updated');
    await post('hit-1', 'new comment');
    await del('hit-1', ['comment-1']);

    expect(mockHget).toHaveBeenCalledWith('/api/v1/hit/hit-1/comments/comment-1');
    expect(mockHput).toHaveBeenCalledWith('/api/v1/hit/hit-1/comments/comment-1', { value: 'updated' });
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/hit/hit-1/comments', { value: 'new comment' });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/hit/hit-1/comments', ['comment-1']);
    expect(react).toEqual({ sentinel: 'react' });
  });
});
