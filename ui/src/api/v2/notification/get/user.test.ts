/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHget = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  hget: mockHget,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/v2/notification/get', () => ({
  uri: () => '/api/v2/notification/get'
}));

import { get, uri } from './user';

describe('user notifications API', () => {
  beforeEach(() => {
    mockHget.mockReset();
  });

  it('builds the user notifications URI', () => {
    expect(uri()).toBe('/api/v2/notification/get/user');
  });

  it('omits pagination parameters when none are provided', () => {
    get();

    expect(mockHget).toHaveBeenCalledWith('/api/v2/notification/get/user', new URLSearchParams(), undefined, undefined);
  });

  it('sends pagination and the abort signal', () => {
    const signal = new AbortController().signal;

    get({ offset: 10, rows: 5 }, signal);

    expect(mockHget).toHaveBeenCalledWith(
      '/api/v2/notification/get/user',
      new URLSearchParams({ offset: '10', rows: '5' }),
      undefined,
      signal
    );
  });
});
