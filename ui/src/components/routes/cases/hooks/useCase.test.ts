import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { createElement } from 'react';
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

const CaseConsumers = ({ case: providedCase }: { case: ReturnType<typeof createMockCase> }) => {
  const sidebarCase = useCase({ case: providedCase });
  const dashboardCase = useCase({ case: providedCase });
  const detailsCase = useCase({ case: providedCase });

  return createElement(
    'div',
    null,
    createElement('span', { id: 'sidebar-case-title' }, sidebarCase.case.title),
    createElement('span', { id: 'dashboard-case-title' }, dashboardCase.case.title),
    createElement('span', { id: 'details-case-title' }, detailsCase.case.title)
  );
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
    it('registers a listener keyed by case ID and hook instance', () => {
      const mockCase = createMockCase({ case_id: 'c3' });
      renderUseCaseHook({ case: mockCase });

      expect(mockAddListener).toHaveBeenCalledWith(expect.stringMatching(/^case-update-c3-/), expect.any(Function));
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

    it('refetches when a socket update contains only the case ID', async () => {
      const mockCase = createMockCase({ case_id: 'c4-minimal', title: 'Original' });
      const fetchedCase = createMockCase({ case_id: 'c4-minimal', title: 'Updated securely' });
      mockDispatchApi.mockResolvedValue(fetchedCase);
      const { result } = renderUseCaseHook({ case: mockCase });

      const listenerCallback = mockAddListener.mock.calls[0][1];

      act(() => {
        listenerCallback({
          type: 'cases',
          case: { case_id: 'c4-minimal' },
          error: false,
          message: '',
          status: 200
        });
      });

      await waitFor(() => {
        expect(result.current.case.title).toBe('Updated securely');
      });
      expect(mockCaseGet).toHaveBeenCalledWith('c4-minimal');
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

      expect(mockRemoveListener).toHaveBeenCalledWith(expect.stringMatching(/^case-update-c7-/));
    });

    it('updates every concurrent case consumer for the same case', () => {
      const mockCase = createMockCase({ case_id: 'c8', title: 'Original' });
      render(createElement(CaseConsumers, { case: mockCase }));

      const listenerKeys = mockAddListener.mock.calls.map(([key]) => key);
      expect(listenerKeys).toHaveLength(3);
      expect([...new Set(listenerKeys)]).toHaveLength(3);

      const updatedCase = createMockCase({ case_id: 'c8', title: 'Updated via socket' });
      act(() => {
        mockAddListener.mock.calls.forEach(([, listener]) => {
          listener({
            type: 'cases',
            case: updatedCase,
            error: false,
            message: '',
            status: 200
          });
        });
      });

      expect(screen.getByTestId('sidebar-case-title')).toHaveTextContent('Updated via socket');
      expect(screen.getByTestId('dashboard-case-title')).toHaveTextContent('Updated via socket');
      expect(screen.getByTestId('details-case-title')).toHaveTextContent('Updated via socket');
    });
  });
});
