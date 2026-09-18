import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hput: mockHput,
  joinUri: mockJoinUri
}));

vi.mock('api/hit/comments', () => ({
  uri: (hit: string, comment: string) => `/api/v1/hit/${hit}/comments/${comment}`
}));

import { del, put, uri } from './react';

describe('hit comment reactions API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHput.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds nested reaction URIs and performs add/remove requests', async () => {
    expect(uri('hit-1', 'comment-1')).toBe('/api/v1/hit/hit-1/comments/comment-1/react');
    await put('hit-1', 'comment-1', 'thumbs_up');
    await del('hit-1', 'comment-1');
    expect(mockHput).toHaveBeenCalledWith('/api/v1/hit/hit-1/comments/comment-1/react', { type: 'thumbs_up' });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/hit/hit-1/comments/comment-1/react');
  });
});
