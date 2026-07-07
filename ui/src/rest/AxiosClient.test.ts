/// <reference types="vitest" />
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AxiosClient from './AxiosClient';

// ---------------------------------------------------------------------------
// vi.hoisted() ensures these values are available when the vi.mock factories
// run (which happens before any module code executes).
// ---------------------------------------------------------------------------
const {
  mockAxiosInstance,
  mockAxiosError,
  mockInterceptorResponseUse,
  interceptorRef
} = vi.hoisted(() => {
  // Ref object used to capture the response interceptor across test resets
  const _interceptorRef: { fn: ((res: any) => Promise<any>) | null } = { fn: null };

  const _mockInterceptorResponseUse = vi.fn().mockImplementation(
    (onFulfilled: (res: any) => Promise<any>) => {
      _interceptorRef.fn = onFulfilled;
    }
  );

  const _mockAxiosInstance = vi.fn() as any;
  _mockAxiosInstance.interceptors = {
    response: { use: _mockInterceptorResponseUse }
  };

  class MockAxiosError extends Error {
    response?: { data: any; status: number; headers: Record<string, any> };
    constructor(message: string, response?: MockAxiosError['response']) {
      super(message);
      this.name = 'AxiosError';
      this.response = response;
    }
  }

  return {
    mockAxiosInstance: _mockAxiosInstance,
    mockAxiosError: MockAxiosError,
    mockInterceptorResponseUse: _mockInterceptorResponseUse,
    interceptorRef: _interceptorRef
  };
});

vi.mock('axios', () => ({
  default: { create: vi.fn(() => mockAxiosInstance) },
  AxiosError: mockAxiosError
}));

vi.mock('axios-retry', () => ({
  default: vi.fn(),
  exponentialDelay: vi.fn(),
  isNetworkError: vi.fn()
}));

vi.mock('utils/sessionStorage', () => ({
  getAxiosCache: vi.fn(() => ({})),
  setAxiosCache: vi.fn()
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AxiosClient', () => {
  let client: AxiosClient;

  beforeEach(() => {
    interceptorRef.fn = null;
    client = new AxiosClient();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // fetch() – happy paths
  // -------------------------------------------------------------------------
  describe('fetch() – successful responses', () => {
    it('returns [data, status, headers] on a 200 response', async () => {
      const payload = { api_response: { items: [] } };
      mockAxiosInstance.mockResolvedValueOnce({
        data: payload,
        status: 200,
        headers: { 'content-type': 'application/json' }
      });

      const result = await client.fetch('/api/v1/hit');
      expect(result[0]).toEqual(payload);
      expect(result[1]).toBe(200);
    });

    it('uses GET as the default HTTP method', async () => {
      mockAxiosInstance.mockResolvedValueOnce({ data: {}, status: 200, headers: {} });
      await client.fetch('/api/v1/hit');
      const config = mockAxiosInstance.mock.calls[0][0];
      expect(config.method).toBe('get');
    });

    it('passes POST as the HTTP method when specified', async () => {
      mockAxiosInstance.mockResolvedValueOnce({ data: {}, status: 201, headers: {} });
      await client.fetch('/api/v1/hit', 'post', { key: 'val' });
      const config = mockAxiosInstance.mock.calls[0][0];
      expect(config.method).toBe('post');
    });

    it('serialises the body as a JSON string', async () => {
      mockAxiosInstance.mockResolvedValueOnce({ data: {}, status: 200, headers: {} });
      await client.fetch('/api/v1/hit', 'post', { status: 'open' });
      const config = mockAxiosInstance.mock.calls[0][0];
      expect(config.data).toBe(JSON.stringify({ status: 'open' }));
    });

    it('passes URLSearchParams through as params', async () => {
      mockAxiosInstance.mockResolvedValueOnce({ data: {}, status: 200, headers: {} });
      const params = new URLSearchParams({ q: 'test' });
      await client.fetch('/api/v1/hit', 'get', undefined, params);
      const config = mockAxiosInstance.mock.calls[0][0];
      expect(config.params).toBe(params);
    });

    it('forwards custom headers', async () => {
      mockAxiosInstance.mockResolvedValueOnce({ data: {}, status: 200, headers: {} });
      const headers = { Authorization: '******' };
      await client.fetch('/api/v1/hit', 'get', undefined, undefined, headers);
      const config = mockAxiosInstance.mock.calls[0][0];
      expect(config.headers).toEqual(headers);
    });

    it('sets withCredentials to true', async () => {
      mockAxiosInstance.mockResolvedValueOnce({ data: {}, status: 200, headers: {} });
      await client.fetch('/api/v1/hit');
      const config = mockAxiosInstance.mock.calls[0][0];
      expect(config.withCredentials).toBe(true);
    });

    it('passes the URL through to the axios config', async () => {
      mockAxiosInstance.mockResolvedValueOnce({ data: {}, status: 200, headers: {} });
      await client.fetch('/api/v1/test-url');
      const config = mockAxiosInstance.mock.calls[0][0];
      expect(config.url).toBe('/api/v1/test-url');
    });
  });

  // -------------------------------------------------------------------------
  // fetch() – error handling
  // -------------------------------------------------------------------------
  describe('fetch() – error handling', () => {
    it('returns [data, status, headers] when the error is an AxiosError with a response', async () => {
      const errorResponse = { data: { error: 'not found' }, status: 404, headers: {} };
      const axiosErr = new mockAxiosError('Not Found', errorResponse);
      mockAxiosInstance.mockRejectedValueOnce(axiosErr);

      const result = await client.fetch('/api/v1/missing');
      expect(result[0]).toEqual({ error: 'not found' });
      expect(result[1]).toBe(404);
    });

    it('rethrows non-AxiosError exceptions', async () => {
      mockAxiosInstance.mockRejectedValueOnce(new TypeError('network failure'));
      await expect(client.fetch('/api/v1/hit')).rejects.toThrow('network failure');
    });

    it('rethrows AxiosError that has no response body', async () => {
      // AxiosError without a .response property → condition `e.response?.data` is falsy → rethrow
      const axiosErr = new mockAxiosError('timeout');
      mockAxiosInstance.mockRejectedValueOnce(axiosErr);
      await expect(client.fetch('/api/v1/hit')).rejects.toThrow('timeout');
    });
  });

  // -------------------------------------------------------------------------
  // AxiosCache – response interceptor
  // -------------------------------------------------------------------------
  describe('AxiosCache response interceptor', () => {
    it('is registered on the axios instance during construction', () => {
      expect(mockInterceptorResponseUse).toHaveBeenCalled();
      expect(interceptorRef.fn).toBeTypeOf('function');
    });

    it('stores a new etag cache entry on a 2xx response with an etag header', async () => {
      const { setAxiosCache } = await import('utils/sessionStorage');
      const res = {
        status: 200,
        headers: { etag: '"abc123"' },
        data: { value: 1 },
        config: { headers: {} }
      };
      await interceptorRef.fn!(res);
      expect(setAxiosCache).toHaveBeenCalledWith('"abc123"', { value: 1 });
    });

    it('replaces data from cache on a 304 response', async () => {
      const { getAxiosCache } = await import('utils/sessionStorage');
      (getAxiosCache as ReturnType<typeof vi.fn>).mockReturnValueOnce({ '"etag-v1"': { cached: true } });

      const res = {
        status: 304,
        headers: {},
        data: null,
        config: { headers: { 'If-Match': '"etag-v1"' } }
      };
      const result = await interceptorRef.fn!(res);
      expect(result.data).toEqual({ cached: true });
    });

    it('passes through a 2xx response without an etag without caching', async () => {
      const { setAxiosCache } = await import('utils/sessionStorage');
      const res = {
        status: 200,
        headers: {},
        data: { ok: true },
        config: { headers: {} }
      };
      await interceptorRef.fn!(res);
      expect(setAxiosCache).not.toHaveBeenCalled();
    });
  });
});
