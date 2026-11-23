/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());
const mockHpost = vi.hoisted(() => vi.fn());
const mockHdelete = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  hdelete: mockHdelete,
  hget: mockHget,
  hpost: mockHpost,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/v2', () => ({
  uri: () => '/api/v2'
}));

vi.mock('api/v2/notification/read', () => ({ sentinel: 'read' }));

import { del, get, post, read, uri } from './index';

describe('notification API', () => {
  beforeEach(() => {
    mockHget.mockReset();
    mockHpost.mockReset();
    mockHdelete.mockReset();
  });

  it('builds the notification URI and re-exports nested modules', () => {
    expect(uri()).toBe('/api/v2/notification');
    expect(uri('n-1')).toBe('/api/v2/notification/n-1');
    expect(read).toEqual({ sentinel: 'read' });
  });

  it('omits pagination parameters when none are provided', () => {
    get();

    expect(mockHget).toHaveBeenCalledWith('/api/v2/notification', new URLSearchParams(), undefined, undefined);
  });

  it('sends pagination and the abort signal', () => {
    const signal = new AbortController().signal;

    get({ offset: 10, rows: 5 }, signal);

    expect(mockHget).toHaveBeenCalledWith(
      '/api/v2/notification',
      new URLSearchParams({ offset: '10', rows: '5' }),
      undefined,
      signal
    );
  });

  it('deletes a notification', () => {
    del('n-1');

    expect(mockHdelete).toHaveBeenCalledWith('/api/v2/notification/n-1');
  });

  it('notifies an analytic owner about a commenter', () => {
    post('an-1', 'demo');

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/notification', {
      analytic_id: 'an-1',
      commenter: 'demo'
    });
  });
});
