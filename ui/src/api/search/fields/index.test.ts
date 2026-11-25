/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest';

vi.mock('api', () => ({
  joinUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/search', () => ({
  uri: () => '/api/v1/search'
}));

vi.mock('api/search/fields/hit', () => ({ token: 'hit' }));
vi.mock('api/search/fields/user', () => ({ token: 'user' }));

import * as fields from './index';

describe('api/search/fields', () => {
  it('builds the fields URI', () => {
    expect(fields.uri()).toBe('/api/v1/search/fields');
  });

  it('maps field objects and filters indexed fields', () => {
    const input = {
      alpha: { default: true, indexed: true, list: false, stored: true, type: 'keyword', description: 'A' },
      beta: { default: false, indexed: false, list: true, stored: false, type: 'text', description: 'B' }
    };

    expect(fields.map(input)).toEqual([
      { key: 'alpha', default: true, indexed: true, list: false, stored: true, type: 'keyword', description: 'A' },
      { key: 'beta', default: false, indexed: false, list: true, stored: false, type: 'text', description: 'B' }
    ]);
    expect(fields.indexed(input)).toEqual([
      { key: 'alpha', default: true, indexed: true, list: false, stored: true, type: 'keyword', description: 'A' }
    ]);
    expect(fields.hit).toEqual({ token: 'hit' });
    expect(fields.user).toEqual({ token: 'user' });
  });
});
