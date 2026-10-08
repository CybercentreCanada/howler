import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  hget: mockHget,
  joinUri: mockJoinUri
}));

vi.mock('api/v2', () => ({
  uri: () => '/api/v2'
}));

import { search, uri } from './index';

describe('v2 task API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinUri.mockClear();
  });

  it('builds the task search URI', () => {
    expect(uri()).toBe('/api/v2/task/search');
  });

  it('sends offset, page size, filter, and abort signal as query parameters', async () => {
    const signal = new AbortController().signal;
    const request = { offset: 25, rows: 25, filter: 'complete' as const };

    await search(request, signal);

    expect(mockHget).toHaveBeenCalledWith(
      '/api/v2/task/search',
      new URLSearchParams({ offset: '25', rows: '25', filter: 'complete' }),
      undefined,
      signal
    );
  });
});
