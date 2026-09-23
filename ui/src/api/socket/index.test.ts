import { describe, expect, it, vi } from 'vitest';

const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));

vi.mock('api', () => ({
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/socket/viewers', () => ({
  sentinel: 'viewers'
}));

import { uri, viewers } from './index';

describe('socket API', () => {
  it('builds the socket root URI and re-exports viewers', () => {
    expect(uri()).toBe('/socket/v1');
    expect(viewers).toEqual({ sentinel: 'viewers' });
  });
});
