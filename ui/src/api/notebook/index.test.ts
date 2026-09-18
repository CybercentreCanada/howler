import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hpost: mockHpost,
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('api/notebook/environments', () => ({
  sentinel: 'environments'
}));

import { environments, post, uri } from './index';

describe('notebook API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the notebook URI and posts notebook requests', async () => {
    await post({ link: 'https://example.com', analytic: { name: 'a' } as any });

    expect(uri()).toBe('/api/v1/notebook');
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1', 'notebook');
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/notebook/notebook', {
      link: 'https://example.com',
      analytic: { name: 'a' }
    });
    expect(environments).toEqual({ sentinel: 'environments' });
  });
});
