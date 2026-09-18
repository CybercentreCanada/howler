import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/overview'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

import { del, get, post, put, uri } from './index';

describe('overview API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail overview URIs', () => {
    expect(uri()).toBe('/api/v1/overview');
    expect(uri('overview-1')).toBe('/api/v1/overview/overview-1');
  });

  it('gets, creates, updates, and deletes overviews', async () => {
    const refresh = new URLSearchParams({ refresh: 'true' });
    await get();
    await post({ content: 'new' } as any, 'true');
    await put('overview-1', 'markdown', 'true');
    await del('overview-1', 'true');

    expect(mockHget).toHaveBeenCalledWith('/api/v1/overview');
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/overview', { content: 'new' }, undefined, refresh);
    expect(mockHput).toHaveBeenCalledWith('/api/v1/overview/overview-1', { content: 'markdown' }, undefined, refresh);
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/overview/overview-1', undefined, undefined, refresh);
  });
});
