import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHdelete = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((base: string, part: string) => `${base}/${part}`));

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hpost: mockHpost,
  joinUri: mockJoinUri
}));

vi.mock('api/analytic', () => ({
  uri: (analytic: string) => `/api/v1/analytic/${analytic}`
}));

import { del, post, uri } from './index';

describe('analytic notebooks API', () => {
  beforeEach(() => {
    mockHdelete.mockReset();
    mockHpost.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the notebooks URI and performs create/delete requests', async () => {
    expect(uri('an-1')).toBe('/api/v1/analytic/an-1/notebooks');
    await post('an-1', { detection: 'det', value: 'link', name: 'Notebook' });
    await del('an-1', ['n-1']);
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/analytic/an-1/notebooks', { detection: 'det', value: 'link', name: 'Notebook' });
    expect(mockHdelete).toHaveBeenCalledWith('/api/v1/analytic/an-1/notebooks', ['n-1']);
  });
});
