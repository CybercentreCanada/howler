/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest';

const mockPost = vi.hoisted(() =>
  vi.fn((url: string, body: any, headers?: any, params?: URLSearchParams) => ({ url, body, headers, params }))
);

vi.mock('api', () => ({
  hpost: mockPost,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/analytic', () => ({
  uri: () => '/api/v1/analytic'
}));

import * as owner from './owner';

describe('api/analytic/owner', () => {
  it('builds owner routes and refresh-aware requests', () => {
    expect(owner.uri('abc')).toBe('/api/v1/analytic/abc/owner');
    expect(owner.post('abc', { username: 'alice' })).toEqual({
      url: '/api/v1/analytic/abc/owner',
      body: { username: 'alice' },
      headers: undefined,
      params: undefined
    });

    const withRefresh = owner.post('abc', { username: 'alice' }, 'wait_for');
    expect(withRefresh.url).toBe('/api/v1/analytic/abc/owner');
    expect(withRefresh.params.toString()).toBe('refresh=wait_for');
  });
});
