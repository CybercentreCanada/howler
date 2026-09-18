import { describe, expect, it, vi } from 'vitest';

const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/auth'));

vi.mock('api', () => ({
  joinUri: mockJoinUri,
  uri: () => '/api/v1'
}));

vi.mock('api/auth/apikey', () => ({
  sentinel: 'apikey'
}));

vi.mock('api/auth/login', () => ({
  sentinel: 'login'
}));

import { apikey, login, uri } from './index';

describe('auth API', () => {
  it('builds the auth URI and re-exports auth modules', () => {
    expect(uri()).toBe('/api/v1/auth');
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1', 'auth');
    expect(apikey).toEqual({ sentinel: 'apikey' });
    expect(login).toEqual({ sentinel: 'login' });
  });
});
