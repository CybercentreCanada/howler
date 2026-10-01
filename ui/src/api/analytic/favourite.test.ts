/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest';

const mockDelete = vi.hoisted(() => vi.fn((url: string) => ({ method: 'delete', url })));
const mockPost = vi.hoisted(() => vi.fn((url: string, body: any) => ({ method: 'post', url, body })));

vi.mock('api', () => ({
  hdelete: mockDelete,
  hpost: mockPost,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/analytic', () => ({
  uri: () => '/api/v1/analytic'
}));

import * as favourite from './favourite';

describe('api/analytic/favourite', () => {
  it('builds favourite routes and requests', () => {
    expect(favourite.uri('abc')).toBe('/api/v1/analytic/abc/favourite');
    expect(favourite.del('abc')).toEqual({ method: 'delete', url: '/api/v1/analytic/abc/favourite' });
    expect(favourite.post('abc')).toEqual({ method: 'post', url: '/api/v1/analytic/abc/favourite', body: {} });
  });
});
