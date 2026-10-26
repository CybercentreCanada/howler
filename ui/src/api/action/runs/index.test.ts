import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockJoinAllUri = vi.hoisted(() => vi.fn((...parts: string[]) => parts.join('/')));

vi.mock('api', () => ({
  hget: mockHget,
  joinAllUri: mockJoinAllUri
}));

vi.mock('api/action', () => ({
  uri: () => '/api/v1/action'
}));

import { get, list, uri } from './index';

describe('action runs API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockJoinAllUri.mockClear();
  });

  it('uses the runs hierarchy for list and detail endpoints', async () => {
    const response = { items: [], offset: 0, rows: 20, has_more: false };
    mockHget.mockResolvedValue(response);

    expect(uri()).toBe('/api/v1/action/runs');
    expect(uri('run-1')).toBe('/api/v1/action/runs/run-1');
    await list({ operation_id: 'ai_triage', action_id: 'action-1', offset: 0, rows: 20 });
    await get('run-1');

    expect(mockHget).toHaveBeenNthCalledWith(
      1,
      '/api/v1/action/runs',
      new URLSearchParams({ operation_id: 'ai_triage', action_id: 'action-1', offset: '0', rows: '20' })
    );
    expect(mockHget).toHaveBeenNthCalledWith(2, '/api/v1/action/runs/run-1');
  });
});
