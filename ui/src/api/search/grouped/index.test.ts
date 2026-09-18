/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest';

vi.mock('api', () => ({
  joinUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/search', () => ({
  uri: () => '/api/v1/search'
}));

vi.mock('api/search/grouped/hit', () => ({ kind: 'hit' }));
vi.mock('api/search/grouped/user', () => ({ kind: 'user' }));

import * as grouped from './index';

describe('api/search/grouped', () => {
  it('builds the grouped URI and re-exports grouped helpers', () => {
    expect(grouped.uri()).toBe('/api/v1/search/grouped');
    expect(grouped.hit).toEqual({ kind: 'hit' });
    expect(grouped.user).toEqual({ kind: 'user' });
  });
});
