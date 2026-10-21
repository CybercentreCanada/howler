/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockClientFetch = vi.hoisted(() => vi.fn());
const mockGetLocalStored = vi.hoisted(() => vi.fn());
const mockRemoveLocalStored = vi.hoisted(() => vi.fn());
const mockSaveLoginCredential = vi.hoisted(() => vi.fn());
const mockSetLocalStored = vi.hoisted(() => vi.fn());
const mockLocalStorage = vi.hoisted(() => new Map<string, unknown>());
const mockGetSessionStored = vi.hoisted(() => vi.fn());
const mockSetSessionStored = vi.hoisted(() => vi.fn());
const mockGetXSRFCookie = vi.hoisted(() => vi.fn());
const mockRefreshLogin = vi.hoisted(() => vi.fn());

vi.mock('rest/AxiosClient', () => ({
  default: class AxiosClient {
    fetch = mockClientFetch;
  }
}));

vi.mock('utils/localStorage', () => ({
  getStored: mockGetLocalStored,
  removeStored: mockRemoveLocalStored,
  saveLoginCredential: mockSaveLoginCredential,
  setStored: mockSetLocalStored
}));

vi.mock('utils/sessionStorage', () => ({
  getStored: mockGetSessionStored,
  setStored: mockSetSessionStored
}));

vi.mock('utils/xsrf', () => ({
  default: mockGetXSRFCookie
}));

vi.mock('api/action', () => ({ sentinel: 'action' }));
vi.mock('api/analytic', () => ({ sentinel: 'analytic' }));
vi.mock('api/auth', () => ({ login: { post: mockRefreshLogin }, sentinel: 'auth' }));
vi.mock('api/configs', () => ({ sentinel: 'configs' }));
vi.mock('api/dossier', () => ({ sentinel: 'dossier' }));
vi.mock('api/help', () => ({ sentinel: 'help' }));
vi.mock('api/hit', () => ({ sentinel: 'hit' }));
vi.mock('api/notebook', () => ({ sentinel: 'notebook' }));
vi.mock('api/overview', () => ({ sentinel: 'overview' }));
vi.mock('api/search', () => ({ sentinel: 'search' }));
vi.mock('api/socket', () => ({ sentinel: 'socket' }));
vi.mock('api/template', () => ({ sentinel: 'template' }));
vi.mock('api/user', () => ({ sentinel: 'user' }));
vi.mock('api/v2', () => ({ sentinel: 'v2' }));
vi.mock('api/view', () => ({ sentinel: 'view' }));

import api, {
  hdelete,
  hfetch,
  hget,
  hpatch,
  hpost,
  hput,
  joinAllUri,
  joinParams,
  joinUri,
  setHeaders,
  uri
} from './index';

describe('api root module', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.clear();
    mockGetXSRFCookie.mockReturnValue(null);
    mockGetSessionStored.mockReturnValue({});
    mockGetLocalStored.mockImplementation((key: string) => mockLocalStorage.get(key));
    mockSetLocalStored.mockImplementation((key: string, value: unknown) => {
      mockLocalStorage.set(key, value);
    });
    mockRemoveLocalStored.mockImplementation((key: string) => {
      mockLocalStorage.delete(key);
    });
    mockSaveLoginCredential.mockImplementation(
      (credentials: { app_token?: string; refresh_token?: string; provider?: string }) => {
        if (credentials.app_token) {
          mockLocalStorage.set('app_token', credentials.app_token);
          if (credentials.refresh_token) {
            mockLocalStorage.set('refresh_token', credentials.refresh_token);
            mockLocalStorage.set('provider', credentials.provider);
          }
        } else {
          mockLocalStorage.delete('app_token');
          mockLocalStorage.delete('refresh_token');
          mockLocalStorage.delete('provider');
        }
      }
    );
    history.pushState({}, '', '/hits?q=1');
  });

  it('exposes the API root path and nested modules', () => {
    expect(uri()).toBe('/api/v1');
    expect(api.action).toEqual({ sentinel: 'action' });
    expect(api.auth).toEqual({ login: { post: mockRefreshLogin }, sentinel: 'auth' });
    expect(api.v2).toEqual({ sentinel: 'v2' });
  });

  it('joins URIs, params, and headers consistently', () => {
    expect(joinParams('/api/v1/hit', new URLSearchParams({ q: 'x' }))).toBe('/api/v1/hit?q=x');
    expect(joinParams('/api/v1/hit?sort=asc', new URLSearchParams({ q: 'x' }))).toBe('/api/v1/hit?sort=asc&q=x');
    expect(joinUri('hit', '123')).toBe('/api/v1/hit/123');
    expect(joinUri('/socket', 'updates')).toBe('/socket/updates');
    expect(joinAllUri('/api', 'v1', 'hit')).toBe('/api/v1/hit');
    expect(setHeaders('abc')).toEqual({ 'If-Match': 'abc' });
  });

  it('performs a successful fetch and stores the returned ETag', async () => {
    mockLocalStorage.set('app_token', 'token');
    mockGetSessionStored.mockReturnValue({ 'hit/hit123': '"old-etag"' });
    mockGetXSRFCookie.mockReturnValue('csrf');
    mockClientFetch.mockResolvedValue([{ api_response: { ok: true } }, 200, { etag: '"new-etag"' }]);

    await expect(hfetch('hit/hit123', 'post', { key: 'value' })).resolves.toEqual({ ok: true });

    expect(mockClientFetch).toHaveBeenCalledWith(
      '/api/v1/hit/hit123',
      'post',
      { key: 'value' },
      undefined,
      expect.objectContaining({
        'Content-Type': 'application/json',
        'If-Match': '"old-etag"',
        'X-XSRF-TOKEN': 'csrf',
        Authorization: expect.any(String)
      }),
      undefined
    );
    expect(mockSetSessionStored).toHaveBeenCalledWith('etag', { 'hit/hit123': '"new-etag"' });
  });

  it('returns undefined for empty payloads and accepts 304 responses', async () => {
    mockClientFetch
      .mockResolvedValueOnce([undefined, 204, {}])
      .mockResolvedValueOnce([{ api_response: { unchanged: true } }, 304, {}]);

    await expect(hfetch('/analytic/1')).resolves.toBeUndefined();
    await expect(hfetch('/analytic/1')).resolves.toEqual({ unchanged: true });
  });

  it('refreshes credentials after a 401 when a refresh token is available', async () => {
    mockLocalStorage.set('app_token', 'expired-token');
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockRefreshLogin.mockResolvedValue({ app_token: 'new-token', refresh_token: 'new-refresh' });
    mockClientFetch
      .mockResolvedValueOnce([{ api_error_message: 'unauthorized' }, 401, {}])
      .mockResolvedValueOnce([{ api_response: { retried: true } }, 200, {}]);

    const params = new URLSearchParams({ limit: '5' });
    const signal = new AbortController().signal;
    await expect(
      hfetch(
        '/view/1',
        'post',
        { query: 'test' },
        params,
        { Accept: 'application/json', 'If-Match': '"caller-etag"' },
        signal
      )
    ).resolves.toEqual({
      retried: true
    });

    expect(mockSetLocalStored).toHaveBeenCalledWith('next.location', '/hits');
    expect(mockSetLocalStored).toHaveBeenCalledWith('next.search', '?q=1');
    expect(mockRefreshLogin).toHaveBeenCalledWith({ refresh_token: 'refresh-token', provider: 'oidc' });
    expect(mockSaveLoginCredential).toHaveBeenCalledWith({ app_token: 'new-token', refresh_token: 'new-refresh' });
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      1,
      '/api/v1//view/1',
      'post',
      { query: 'test' },
      params,
      expect.objectContaining({
        Authorization: 'Bearer expired-token',
        Accept: 'application/json',
        'If-Match': '"caller-etag"'
      }),
      signal
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      2,
      '/api/v1//view/1',
      'post',
      { query: 'test' },
      params,
      expect.objectContaining({
        Authorization: 'Bearer new-token',
        Accept: 'application/json',
        'If-Match': '"caller-etag"'
      }),
      signal
    );
    expect(mockRemoveLocalStored).toHaveBeenCalledWith('next.location');
    expect(mockRemoveLocalStored).toHaveBeenCalledWith('next.search');
  });

  it.each([
    ['empty', undefined],
    ['blank token', { app_token: '   ' }],
    ['unchanged', { app_token: 'expired-token' }]
  ])('does not replay after an %s refresh response', async (_description, refreshResponse) => {
    mockLocalStorage.set('app_token', 'expired-token');
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockRefreshLogin.mockResolvedValue(refreshResponse);
    mockClientFetch.mockResolvedValue([{ api_error_message: 'unauthorized' }, 401, {}]);
    history.pushState({}, '', '/login?auth=1');

    await expect(hfetch('/view/1')).resolves.toBeUndefined();

    expect(mockClientFetch).toHaveBeenCalledTimes(1);
    expect(mockRefreshLogin).toHaveBeenCalledTimes(1);
    expect(mockSaveLoginCredential).toHaveBeenLastCalledWith({});
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.location');
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.search');
  });

  it('does not refresh again or clear the saved return route when the replay is unauthorized', async () => {
    mockLocalStorage.set('app_token', 'expired-token');
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockRefreshLogin.mockResolvedValue({ app_token: 'new-token' });
    mockClientFetch.mockResolvedValue([{ api_error_message: 'unauthorized' }, 401, {}]);
    history.pushState({}, '', '/login?auth=1');

    await expect(hfetch('/view/1')).resolves.toBeUndefined();

    expect(mockClientFetch).toHaveBeenCalledTimes(2);
    expect(mockRefreshLogin).toHaveBeenCalledTimes(1);
    expect(mockSaveLoginCredential).toHaveBeenLastCalledWith({});
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.location');
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.search');
  });

  it('clears the saved return route after an empty successful replay response', async () => {
    mockLocalStorage.set('app_token', 'expired-token');
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockRefreshLogin.mockResolvedValue({ app_token: 'new-token' });
    mockClientFetch
      .mockResolvedValueOnce([{ api_error_message: 'unauthorized' }, 401, {}])
      .mockResolvedValueOnce([undefined, 204, {}]);

    await expect(hfetch('/view/1')).resolves.toBeUndefined();

    expect(mockClientFetch).toHaveBeenCalledTimes(2);
    expect(mockRefreshLogin).toHaveBeenCalledTimes(1);
    expect(mockRemoveLocalStored).toHaveBeenCalledWith('next.location');
    expect(mockRemoveLocalStored).toHaveBeenCalledWith('next.search');
  });

  it('does not clear the saved return route after an empty unauthorized replay response', async () => {
    mockLocalStorage.set('app_token', 'expired-token');
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockRefreshLogin.mockResolvedValue({ app_token: 'new-token' });
    mockClientFetch
      .mockResolvedValueOnce([{ api_error_message: 'unauthorized' }, 401, {}])
      .mockResolvedValueOnce([undefined, 401, {}]);

    await expect(hfetch('/view/1')).resolves.toBeUndefined();

    expect(mockClientFetch).toHaveBeenCalledTimes(2);
    expect(mockRefreshLogin).toHaveBeenCalledTimes(1);
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.location');
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.search');
  });

  it('does not replay if refreshed credentials were not persisted', async () => {
    mockLocalStorage.set('app_token', 'expired-token');
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockRefreshLogin.mockResolvedValue({ app_token: 'new-token' });
    mockSaveLoginCredential.mockImplementationOnce(() => {});
    mockClientFetch.mockResolvedValue([{ api_error_message: 'unauthorized' }, 401, {}]);
    history.pushState({}, '', '/login?auth=1');

    await expect(hfetch('/view/1')).resolves.toBeUndefined();

    expect(mockClientFetch).toHaveBeenCalledTimes(1);
    expect(mockSaveLoginCredential).toHaveBeenNthCalledWith(1, { app_token: 'new-token' });
    expect(mockSaveLoginCredential).toHaveBeenNthCalledWith(2, {});
  });

  it('propagates a rejected refresh request without replaying the original request', async () => {
    mockLocalStorage.set('app_token', 'expired-token');
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockRefreshLogin.mockRejectedValue(new Error('refresh failed'));
    mockClientFetch.mockResolvedValue([{ api_error_message: 'unauthorized' }, 401, {}]);

    await expect(hfetch('/view/1')).rejects.toThrow('refresh failed');

    expect(mockClientFetch).toHaveBeenCalledTimes(1);
    expect(mockRefreshLogin).toHaveBeenCalledTimes(1);
    expect(mockSaveLoginCredential).not.toHaveBeenCalled();
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.location');
    expect(mockRemoveLocalStored).not.toHaveBeenCalledWith('next.search');
  });

  it('does not try to refresh an unauthorized login request', async () => {
    mockLocalStorage.set('refresh_token', 'refresh-token');
    mockLocalStorage.set('provider', 'oidc');
    mockClientFetch.mockResolvedValue([{ api_error_message: 'unauthorized' }, 401, {}]);
    history.pushState({}, '', '/login?auth=1');

    await expect(hfetch('/auth/login')).resolves.toBeUndefined();

    expect(mockClientFetch).toHaveBeenCalledTimes(1);
    expect(mockRefreshLogin).not.toHaveBeenCalled();
  });

  it('clears credentials after a 401 when refresh is unavailable', async () => {
    history.pushState({}, '', '/login');
    mockClientFetch.mockResolvedValue([{ api_error_message: 'unauthorized' }, 401, {}]);

    await expect(hfetch('/auth/login')).resolves.toBeUndefined();

    expect(mockSaveLoginCredential).toHaveBeenCalledWith({});
  });

  it('throws the API error message for non-401 failures', async () => {
    mockClientFetch.mockResolvedValue([{ api_error_message: 'boom' }, 500, {}]);

    await expect(hfetch('/hit/1')).rejects.toThrow('boom');
  });

  it('delegates convenience wrappers to hfetch with the expected methods', async () => {
    mockClientFetch.mockResolvedValue([{ api_response: undefined }, 200, {}]);

    await hget('/x', new URLSearchParams({ a: '1' }), { Accept: 'json' });
    await hpost('/x', { ok: true }, { A: '1' }, new URLSearchParams({ b: '2' }));
    await hput('/x', { ok: true }, { A: '1' }, new URLSearchParams({ b: '2' }));
    await hpatch('/x', { ok: true }, { A: '1' }, new URLSearchParams({ b: '2' }));
    await hdelete('/x', { ok: true }, { A: '1' }, new URLSearchParams({ b: '2' }));

    expect(mockClientFetch).toHaveBeenNthCalledWith(
      1,
      '/api/v1//x',
      'get',
      null,
      new URLSearchParams({ a: '1' }),
      expect.objectContaining({ Accept: 'json', 'Content-Type': 'application/json' }),
      undefined
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      2,
      '/api/v1//x',
      'post',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' }),
      undefined
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      3,
      '/api/v1//x',
      'put',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' }),
      undefined
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      4,
      '/api/v1//x',
      'patch',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' }),
      undefined
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      5,
      '/api/v1//x',
      'delete',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' }),
      undefined
    );
  });
});
