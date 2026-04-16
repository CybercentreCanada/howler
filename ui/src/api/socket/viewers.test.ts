import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockHget = vi.hoisted(() => vi.fn());

vi.mock('api', async () => {
  const urlJoin = (await import('url-join')).default;
  return {
    hget: mockHget,
    joinAllUri: (...parts: string[]) => urlJoin(...parts)
  };
});

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

// eslint-disable-next-line
import { get } from './viewers';

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockHget.mockReset();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('viewers API', () => {
  describe('get', () => {
    it('calls hget with the correct URI', async () => {
      mockHget.mockResolvedValue(['alice', 'bob']);

      await get('entity-1');

      expect(mockHget).toHaveBeenCalledWith('/socket/v1/viewers/entity-1');
    });

    it('returns the result from hget', async () => {
      mockHget.mockResolvedValue(['alice', 'bob']);

      const result = await get('entity-1');

      expect(result).toEqual(['alice', 'bob']);
    });

    it('propagates errors from hget', async () => {
      mockHget.mockRejectedValue(new Error('not found'));

      await expect(get('entity-1')).rejects.toThrow('not found');
    });
  });
});
