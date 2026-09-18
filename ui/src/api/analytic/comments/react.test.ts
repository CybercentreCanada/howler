import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hput: mockHput,
  joinUri: mockJoinUri
}));

vi.mock('api/analytic/comments', () => ({
  uri: (analytic: string, comment: string) => `/api/v1/analytic/${analytic}/comments/${comment}`
}));

import { del, put, uri } from './react';

describe('analytic comment reactions API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHput.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds nested reaction URIs and performs add/remove requests', async () => {
    expect(uri('an-1', 'c-1')).toBe('/api/v1/analytic/an-1/comments/c-1/react');
    await put('an-1', 'c-1', 'thumbs_up');
    await del('an-1', 'c-1');
    expect(mockHput).toHaveBeenCalledWith('/api/v1/analytic/an-1/comments/c-1/react', { type: 'thumbs_up' });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/analytic/an-1/comments/c-1/react');
  });
});
