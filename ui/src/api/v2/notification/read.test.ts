/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockHput = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  hput: mockHput,
  joinAllUri: (...parts: string[]) => parts.join('/')
}));

vi.mock('api/v2/notification', () => ({
  uri: () => '/api/v2/notification'
}));

import { put, uri } from './read';

describe('notification read API', () => {
  beforeEach(() => {
    mockHput.mockReset();
  });

  it('builds the read URI for a notification', () => {
    expect(uri('n-1')).toBe('/api/v2/notification/n-1/read');
  });

  it('marks the notification as read', () => {
    put('n-1', true);

    expect(mockHput).toHaveBeenCalledWith('/api/v2/notification/n-1/read', { read: true });
  });

  it('marks the notification as unread', () => {
    put('n-1', false);

    expect(mockHput).toHaveBeenCalledWith('/api/v2/notification/n-1/read', { read: false });
  });
});
