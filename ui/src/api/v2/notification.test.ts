/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  hpost: mockHpost,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/v2', () => ({
  uri: () => '/api/v2'
}));

import { notify, uri } from './notification';

describe('notification API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
  });

  it('notifies an analytic owner about a commenter', () => {
    notify('an-1', 'demo');

    expect(uri()).toBe('/api/v2/notification/notify');
    expect(mockHpost).toHaveBeenCalledWith('/api/v2/notification/notify', {
      analytic_id: 'an-1',
      commenter: 'demo'
    });
  });
});
