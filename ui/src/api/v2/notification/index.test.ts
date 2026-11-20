/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());
const mockHdelete = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hpost: mockHpost,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/v2', () => ({
  uri: () => '/api/v2'
}));

vi.mock('api/v2/notification/get', () => ({ sentinel: 'get' }));
vi.mock('api/v2/notification/read', () => ({ sentinel: 'read' }));

import { del, get, notify, read, uri } from './index';

describe('notification API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
    mockHdelete.mockReset();
  });

  it('builds the notification URI and re-exports nested modules', () => {
    expect(uri()).toBe('/api/v2/notification');
    expect(uri('n-1')).toBe('/api/v2/notification/n-1');
    expect(get).toEqual({ sentinel: 'get' });
    expect(read).toEqual({ sentinel: 'read' });
  });

  it('deletes a notification', () => {
    del('n-1');

    expect(mockHdelete).toHaveBeenCalledWith('/api/v2/notification/n-1');
  });

  it('notifies an analytic owner about a commenter', () => {
    notify('an-1', 'demo');

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/notification/notify', {
      analytic_id: 'an-1',
      commenter: 'demo'
    });
  });
});
