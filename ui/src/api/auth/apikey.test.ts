import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hpost: mockHpost,
  joinUri: mockJoinUri
}));

vi.mock('api/auth', () => ({
  uri: () => '/api/v1/auth'
}));

import { del, post, uri } from './apikey';

describe('auth apikey API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHpost.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds list and detail API key URIs', () => {
    expect(uri()).toBe('/api/v1/auth/apikey');
    expect(uri('demo')).toBe('/api/v1/auth/apikey/demo');
  });

  it('creates and deletes API keys', async () => {
    await post('demo', ['R', 'W'], '2026-10-10');
    await del('demo');

    expect(mockHpost).toHaveBeenCalledWith('/api/v1/auth/apikey', {
      name: 'demo',
      priv: ['R', 'W'],
      expiry_date: '2026-10-10'
    });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/auth/apikey/demo');
  });
});
