/// <reference types="vitest" />
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import FetchClient from './FetchClient';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockFetch = (status: number, body: any, headers: Record<string, string> = {}) => {
  const response = {
    status,
    headers,
    json: vi.fn().mockResolvedValue(body)
  } as unknown as Response;

  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('FetchClient', () => {
  let client: FetchClient;

  beforeEach(() => {
    client = new FetchClient();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('calls fetch with the provided URL and GET method by default', async () => {
    const spy = mockFetch(200, { api_response: 'ok' });
    await client.fetch('/api/v1/test');
    expect(spy).toHaveBeenCalledWith(
      '/api/v1/test',
      expect.objectContaining({ method: 'get', credentials: 'same-origin' })
    );
  });

  it('appends query params to the URL when provided', async () => {
    const spy = mockFetch(200, {});
    const params = new URLSearchParams({ q: 'hello world' });
    await client.fetch('/api/v1/search', 'get', undefined, params);
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('q=hello+world'), expect.anything());
  });

  it('returns [json, status, headers] on a successful response', async () => {
    const payload = { api_response: { items: [] } };
    mockFetch(200, payload);
    const result = await client.fetch('/api/v1/hit');
    expect(result[0]).toEqual(payload);
    expect(result[1]).toBe(200);
  });

  it('serialises the body as JSON when provided', async () => {
    const spy = mockFetch(201, {});
    await client.fetch('/api/v1/hit', 'post', { key: 'val' });
    const callArgs = spy.mock.calls[0][1] as RequestInit;
    expect(callArgs.body).toBe(JSON.stringify({ key: 'val' }));
  });

  it('sends null body when no body is provided', async () => {
    const spy = mockFetch(200, {});
    await client.fetch('/api/v1/hit', 'get');
    const callArgs = spy.mock.calls[0][1] as RequestInit;
    expect(callArgs.body).toBeNull();
  });

  it('forwards custom headers to fetch', async () => {
    const spy = mockFetch(200, {});
    await client.fetch('/api/v1/hit', 'get', undefined, undefined, { Authorization: '******' });
    const callArgs = spy.mock.calls[0][1] as RequestInit;
    expect((callArgs.headers as Record<string, string>).Authorization).toBe('******');
  });

  it('returns null for a 204 No Content response', async () => {
    mockFetch(204, null);
    const result = await client.fetch('/api/v1/hit', 'delete');
    expect(result).toBeNull();
  });

  it('works with a PUT method', async () => {
    const spy = mockFetch(200, {});
    await client.fetch('/api/v1/hit/123', 'put', { status: 'open' });
    expect(spy).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ method: 'put' }));
  });

  it('works with a DELETE method', async () => {
    const spy = mockFetch(200, {});
    await client.fetch('/api/v1/hit/123', 'delete');
    expect(spy).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ method: 'delete' }));
  });

  it('propagates errors thrown by the underlying fetch', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network error'));
    await expect(client.fetch('/api/v1/hit')).rejects.toThrow('network error');
  });
});
