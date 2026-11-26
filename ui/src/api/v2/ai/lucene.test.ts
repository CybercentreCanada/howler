import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { post, uri } from './lucene';

const encoder = new TextEncoder();

const streamResponse = (chunks: string[]) => {
  const pending = chunks.map(chunk => encoder.encode(chunk));
  const cancel = vi.fn(() => Promise.resolve());

  return {
    cancel,
    response: {
      ok: true,
      status: 200,
      body: {
        getReader: () => ({
          read: () =>
            Promise.resolve(
              pending.length ? { done: false, value: pending.shift() } : { done: true, value: undefined }
            ),
          cancel
        })
      }
    }
  };
};

describe('v2 AI lucene API', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('streams text and status events split across chunks and resolves with the final query', async () => {
    mockFetch.mockResolvedValue(
      streamResponse([
        'event: status\ndata: {"status": "Checking fields"}\n\ndata: {"text": "howler.sta',
        'tus:open"}\n\ndata: {"text": "howler.status:open AND x"}\r\n\r\n',
        'event: done\ndata: {"query": "howler.status:open AND x", "warning": "Check it"}\n\n'
      ]).response
    );
    const onText = vi.fn();
    const onStatus = vi.fn();

    await expect(post({ prompt: 'open hits', query: 'a:b' }, { onText, onStatus })).resolves.toEqual({
      query: 'howler.status:open AND x',
      warning: 'Check it'
    });

    expect(uri()).toBe('/api/v2/ai/lucene');
    expect(onStatus.mock.calls).toEqual([['Checking fields']]);
    expect(onText.mock.calls).toEqual([['howler.status:open'], ['howler.status:open AND x']]);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/v2/ai/lucene');
    expect(init).toMatchObject({ method: 'POST', body: JSON.stringify({ prompt: 'open hits', query: 'a:b' }) });
    expect(init.headers.Accept).toBe('text/event-stream');
  });

  it('rejects with the streamed error and cancels the reader', async () => {
    const { response, cancel } = streamResponse([
      'data: {"text": "partial"}\n\nevent: error\ndata: {"error": "Provider response timed out"}\n\n'
    ]);
    mockFetch.mockResolvedValue(response);

    await expect(post({ prompt: 'open hits' })).rejects.toThrow('Provider response timed out');
    expect(cancel).toHaveBeenCalled();
  });

  it('rejects when the stream ends without a final query', async () => {
    mockFetch.mockResolvedValue(streamResponse(['data: {"text": "partial"}\n\n']).response);

    await expect(post({ prompt: 'open hits' })).rejects.toThrow('AI query generation ended unexpectedly.');
  });

  it('surfaces API errors returned before streaming starts', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      body: null,
      json: () => Promise.resolve({ api_error_message: 'AI query generation is not enabled.' })
    });

    await expect(post({ prompt: 'open hits' })).rejects.toThrow('AI query generation is not enabled.');
  });
});
