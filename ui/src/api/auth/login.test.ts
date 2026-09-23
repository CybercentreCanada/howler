import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinUri = vi.hoisted(() => vi.fn((_base: string, _part: string, params?: URLSearchParams) => {
  const base = '/api/v1/auth/login';
  return params ? `${base}?${params.toString()}` : base;
}));

vi.mock('api', () => ({
  hget: mockHget,
  hpost: mockHpost,
  joinUri: mockJoinUri
}));

vi.mock('api/auth', () => ({
  uri: () => '/api/v1/auth'
}));

import { get, post, uri } from './login';
import { MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';

describe('auth login API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockHpost.mockReset();
    mockJoinUri.mockClear();
    localStorage.clear();
  });

  it('builds the login endpoint URI and forwards search params', () => {
    const params = new URLSearchParams({ next: '/hits' });

    expect(uri(params)).toBe('/api/v1/auth/login?next=%2Fhits');
    expect(mockJoinUri).toHaveBeenCalledWith('/api/v1/auth', 'login', params);
  });

  it('posts credentials to the login endpoint', async () => {
    const response = { app_token: 'token' };
    mockHpost.mockResolvedValue(response);

    await expect(post({ user: 'demo', password: 'secret' })).resolves.toEqual(response);
    expect(mockHpost).toHaveBeenCalledWith('/api/v1/auth/login', { user: 'demo', password: 'secret' });
  });

  it('adds and clears the stored OAuth nonce before fetching login state', async () => {
    const params = new URLSearchParams({ code: 'oauth-code' });
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');
    localStorage.setItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.LOGIN_NONCE}`, JSON.stringify('saved-nonce'));
    mockHget.mockResolvedValue({ app_token: 'token' });

    await get(params);

    expect(params.get('nonce')).toBe('saved-nonce');
    expect(removeItemSpy).toHaveBeenCalledWith(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.LOGIN_NONCE}`);
    expect(mockHget).toHaveBeenCalledWith('/api/v1/auth/login', params);
  });

  it('fetches login state unchanged when no nonce is stored', async () => {
    const params = new URLSearchParams({ provider: 'oidc' });
    mockHget.mockResolvedValue({ refresh_token: 'refresh' });

    await get(params);

    expect(params.get('nonce')).toBeNull();
    expect(mockHget).toHaveBeenCalledWith('/api/v1/auth/login', params);
  });
});
