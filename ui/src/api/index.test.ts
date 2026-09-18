/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockClientFetch = vi.hoisted(() => vi.fn());
const mockGetLocalStored = vi.hoisted(() => vi.fn());
const mockRemoveLocalStored = vi.hoisted(() => vi.fn());
const mockSaveLoginCredential = vi.hoisted(() => vi.fn());
const mockSetLocalStored = vi.hoisted(() => vi.fn());
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
    mockGetXSRFCookie.mockReturnValue(null);
    mockGetSessionStored.mockReturnValue({});
    mockGetLocalStored.mockImplementation((key: string) => {
      if (key === 'etag') {
        return undefined;
      }
      return undefined;
    });
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
    mockGetLocalStored.mockImplementation((key: string) => (key === 'app_token' ? 'token' : undefined));
    mockGetSessionStored.mockReturnValue({ 'hit/hit123': '"old-etag"' });
    mockGetXSRFCookie.mockReturnValue('csrf');
    mockClientFetch.mockResolvedValue([
      { api_response: { ok: true } },
      200,
      { etag: '"new-etag"' }
    ]);

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
      })
    );
    expect(mockSetSessionStored).toHaveBeenCalledWith('etag', { 'hit/hit123': '"new-etag"' });
  });

  it('returns undefined for empty payloads and accepts 304 responses', async () => {
    mockClientFetch.mockResolvedValueOnce([undefined, 204, {}]).mockResolvedValueOnce([
      { api_response: { unchanged: true } },
      304,
      {}
    ]);

    await expect(hfetch('/analytic/1')).resolves.toBeUndefined();
    await expect(hfetch('/analytic/1')).resolves.toEqual({ unchanged: true });
  });

  it('refreshes credentials after a 401 when a refresh token is available', async () => {
    mockGetLocalStored.mockImplementation((key: string) => {
      if (key === 'refresh_token') return 'refresh-token';
      if (key === 'provider') return 'oidc';
      return undefined;
    });
    mockRefreshLogin.mockResolvedValue({ app_token: 'new-token', refresh_token: 'new-refresh' });
    mockClientFetch
      .mockResolvedValueOnce([{ api_error_message: 'unauthorized' }, 401, {}])
      .mockResolvedValueOnce([{ api_response: { retried: true } }, 200, {}]);

    await expect(hfetch('/view/1')).resolves.toEqual({ retried: true });

    expect(mockSetLocalStored).toHaveBeenCalledWith('next.location', '/hits');
    expect(mockSetLocalStored).toHaveBeenCalledWith('next.search', '?q=1');
    expect(mockRefreshLogin).toHaveBeenCalledWith({ refresh_token: 'refresh-token', provider: 'oidc' });
    expect(mockSaveLoginCredential).toHaveBeenCalledWith({ app_token: 'new-token', refresh_token: 'new-refresh' });
    expect(mockRemoveLocalStored).toHaveBeenCalledWith('next.location');
    expect(mockRemoveLocalStored).toHaveBeenCalledWith('next.search');
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
      expect.objectContaining({ Accept: 'json', 'Content-Type': 'application/json' })
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      2,
      '/api/v1//x',
      'post',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' })
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      3,
      '/api/v1//x',
      'put',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' })
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      4,
      '/api/v1//x',
      'patch',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' })
    );
    expect(mockClientFetch).toHaveBeenNthCalledWith(
      5,
      '/api/v1//x',
      'delete',
      { ok: true },
      new URLSearchParams({ b: '2' }),
      expect.objectContaining({ A: '1', 'Content-Type': 'application/json' })
    );
  });
});
