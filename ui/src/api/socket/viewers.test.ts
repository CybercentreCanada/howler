import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockFetch = vi.hoisted(() => vi.fn());

vi.mock('rest/AxiosClient', () => ({
  default: vi.fn().mockImplementation(() => ({
    fetch: mockFetch
  }))
}));

const mockGetStored = vi.hoisted(() => vi.fn());

vi.mock('utils/localStorage', () => ({
  getStored: mockGetStored
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

// eslint-disable-next-line
import { get } from './viewers';

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockFetch.mockReset();
  mockGetStored.mockReset();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('viewers API', () => {
  describe('get', () => {
    it('calls fetch with the correct URL', async () => {
      mockGetStored.mockReturnValue('test-token');
      mockFetch.mockResolvedValue([{ api_response: ['alice', 'bob'] }, 200]);

      await get('entity-1');

      expect(mockFetch).toHaveBeenCalledWith(
        '/socket/v1/viewers/entity-1',
        'get',
        undefined,
        undefined,
        expect.objectContaining({ 'Content-Type': 'application/json' })
      );
    });

    it('returns the api_response on success', async () => {
      mockGetStored.mockReturnValue('test-token');
      mockFetch.mockResolvedValue([{ api_response: ['alice', 'bob'] }, 200]);

      const result = await get('entity-1');

      expect(result).toEqual(['alice', 'bob']);
    });

    it('returns empty array on error status', async () => {
      mockGetStored.mockReturnValue('test-token');
      mockFetch.mockResolvedValue([{ api_error_message: 'not found' }, 404]);

      const result = await get('entity-1');

      expect(result).toEqual([]);
    });

    it('includes authorization header when token is available', async () => {
      mockGetStored.mockReturnValue('my-app-token');
      mockFetch.mockResolvedValue([{ api_response: [] }, 200]);

      await get('entity-1');

      const headers = mockFetch.mock.calls[0][4];
      expect(headers.Authorization).toBe('Bearer my-app-token');
    });

    it('omits authorization header when no token', async () => {
      mockGetStored.mockReturnValue(null);
      mockFetch.mockResolvedValue([{ api_response: [] }, 200]);

      await get('entity-1');

      const headers = mockFetch.mock.calls[0][4];
      expect(headers.Authorization).toBeUndefined();
    });
  });
});
