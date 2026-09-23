import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/').replace(/\/+/g, '/')));
const mockJoinUri = vi.hoisted(() => vi.fn(() => '/api/v1/action/execute'));

vi.mock('api', () => ({
  hpost: mockHpost,
  joinAllUri: mockJoinAllUri,
  joinUri: mockJoinUri
}));

vi.mock('api/action', () => ({
  uri: () => '/api/v1/action'
}));

import { post, uri } from './execute';

describe('action execute API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockJoinAllUri.mockClear();
    mockJoinUri.mockClear();
  });

  it('builds collection and detail execute URIs', () => {
    expect(uri()).toBe('/api/v1/action/execute');
    expect(uri('action-1')).toBe('/api/v1/action/action-1/execute');
  });

  it('posts either an existing action execution or an ad-hoc action execution', async () => {
    mockHpost.mockResolvedValue({ success: true });

    await post({ action_id: 'action-1', request_id: 'req-1', query: 'status:open' } as any);
    await post({ request_id: 'req-2', query: 'status:new', operations: [{ operation: 'x' }] } as any);

    expect(mockHpost).toHaveBeenNthCalledWith(1, '/api/v1/action/action-1/execute', {
      request_id: 'req-1',
      query: 'status:open'
    });
    expect(mockHpost).toHaveBeenNthCalledWith(2, '/api/v1/action/execute', {
      request_id: 'req-2',
      query: 'status:new',
      operations: [{ operation: 'x' }]
    });
  });
});
