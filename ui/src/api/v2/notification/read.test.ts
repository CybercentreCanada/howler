/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHpost = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  hpost: mockHpost,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/v2/notification', () => ({
  uri: () => '/api/v2/notification'
}));

import { post, uri } from './read';

describe('notification read API', () => {
  beforeEach(() => {
    mockHpost.mockReset();
  });

  it('builds the read URI for a notification', () => {
    expect(uri('n-1')).toBe('/api/v2/notification/n-1/read');
  });

  it('marks the notification as read', () => {
    post('n-1');

    expect(mockHpost).toHaveBeenCalledWith('/api/v2/notification/n-1/read', null);
  });
});
