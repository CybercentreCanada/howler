import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHput = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v2/case'));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  hput: mockHput,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri
}));

vi.mock('api/v2', () => ({
  uri: () => '/api/v2'
}));

vi.mock('api/v2/case/items', () => ({
  sentinel: 'items'
}));

vi.mock('api/v2/case/rules', () => ({
  sentinel: 'rules'
}));

import { del, get, items, post, put, rules, uri } from './index';

describe('v2 case API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHput.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail URIs', () => {
    expect(uri()).toBe('/api/v2/case');
    expect(uri('case-1')).toBe('/api/v2/case/case-1');
  });

  it('gets, creates, updates, and deletes cases', async () => {
    mockHget.mockResolvedValue({ id: 'case-1' });
    mockHpost.mockResolvedValue({ id: 'case-2' });
    mockHput.mockResolvedValue({ id: 'case-3' });
    mockHdelete.mockResolvedValue(undefined);

    await expect(get('case-1')).resolves.toEqual({ id: 'case-1' });
    await expect(post({ title: 'new case' } as any)).resolves.toEqual({ id: 'case-2' });
    await expect(put('case-3', { title: 'updated' } as any)).resolves.toEqual({ id: 'case-3' });
    await expect(del('case-4')).resolves.toBeUndefined();

    expect(mockHget).toHaveBeenCalledWith('/api/v2/case/case-1');
    expect(mockHpost).toHaveBeenCalledWith('/api/v2/case', { title: 'new case' });
    expect(mockHput).toHaveBeenCalledWith('/api/v2/case/case-3', { title: 'updated' });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v2/case/case-4');
  });

  it('re-exports the nested items and rules APIs', () => {
    expect(items).toEqual({ sentinel: 'items' });
    expect(rules).toEqual({ sentinel: 'rules' });
  });
});
