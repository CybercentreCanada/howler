import { act, renderHook, waitFor } from '@testing-library/react';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockAddListener = vi.hoisted(() => vi.fn());
const mockRemoveListener = vi.hoisted(() => vi.fn());
const mockCaseGet = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: (...args: any[]) => mockCaseGet(...args),
        put: vi.fn()
      }
    }
  }
}));

vi.mock('components/app/providers/SocketProvider', async () => {
  const { createContext } = await import('react');
  return {
    SocketContext: createContext({
      addListener: mockAddListener,
      removeListener: mockRemoveListener,
      emit: vi.fn(),
      status: 1,
      reconnect: vi.fn(),
      isOpen: () => true,
      viewers: {},
      fetchViewers: vi.fn()
    })
  };
});

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

// eslint-disable-next-line
import useCase from './useCase';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const renderUseCaseHook = (args: Parameters<typeof useCase>[0]) => {
  return renderHook(() => useCase(args));
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockAddListener.mockReset();
  mockRemoveListener.mockReset();
  mockCaseGet.mockReset();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useCase', () => {
  describe('initialization', () => {
    it('uses the provided case directly when given', () => {
      const mockCase = createMockCase({ case_id: 'c1', title: 'Provided' });
      const { result } = renderUseCaseHook({ case: mockCase });

      expect(result.current.case).toBe(mockCase);
      expect(result.current.loading).toBe(false);
    });

    it('fetches the case by ID when caseId is provided', async () => {
      const mockCase = createMockCase({ case_id: 'c2', title: 'Fetched' });
      mockDispatchApi.mockResolvedValue(mockCase);

      const { result } = renderUseCaseHook({ caseId: 'c2' });

      await waitFor(() => {
        expect(result.current.case).toEqual(mockCase);
      });

      expect(mockDispatchApi).toHaveBeenCalled();
    });
  });

  describe('socket listener', () => {
    it('registers a listener keyed by case ID', () => {
      const mockCase = createMockCase({ case_id: 'c3' });
      renderUseCaseHook({ case: mockCase });

      expect(mockAddListener).toHaveBeenCalledWith('case-update-c3', expect.any(Function));
    });

    it('updates state when a matching case update is received', () => {
      const mockCase = createMockCase({ case_id: 'c4', title: 'Original' });
      const { result } = renderUseCaseHook({ case: mockCase });

      const listenerCallback = mockAddListener.mock.calls[0][1];
      const updatedCase = createMockCase({ case_id: 'c4', title: 'Updated via socket' });

      act(() => {
        listenerCallback({
          type: 'cases',
          case: updatedCase,
          error: false,
          message: '',
          status: 200
        });
      });

      expect(result.current.case.title).toBe('Updated via socket');
    });

    it('ignores case updates for a different case ID', () => {
      const mockCase = createMockCase({ case_id: 'c5', title: 'Original' });
      const { result } = renderUseCaseHook({ case: mockCase });

      const listenerCallback = mockAddListener.mock.calls[0][1];
      const differentCase = createMockCase({ case_id: 'other-case', title: 'Different' });

      act(() => {
        listenerCallback({
          type: 'cases',
          case: differentCase,
          error: false,
          message: '',
          status: 200
        });
      });

      expect(result.current.case.title).toBe('Original');
    });

    it('ignores non-case-update messages', () => {
      const mockCase = createMockCase({ case_id: 'c6', title: 'Original' });
      const { result } = renderUseCaseHook({ case: mockCase });

      const listenerCallback = mockAddListener.mock.calls[0][1];

      act(() => {
        listenerCallback({
          type: 'hits',
          hit: {},
          version: '1',
          error: false,
          message: '',
          status: 200
        });
      });

      expect(result.current.case.title).toBe('Original');
    });

    it('removes listener on unmount', () => {
      const mockCase = createMockCase({ case_id: 'c7' });
      const { unmount } = renderUseCaseHook({ case: mockCase });

      unmount();

      expect(mockRemoveListener).toHaveBeenCalledWith('case-update-c7');
    });
  });
});
