import { render, waitFor } from '@testing-library/react';
import { SocketContext } from 'components/app/providers/SocketProvider';
import type { ReactNode } from 'react';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockEmit = vi.hoisted(() => vi.fn());
const mockFetchViewers = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockOpen = vi.hoisted(() => ({ current: true }));
const mockAddListener = vi.hoisted(() => vi.fn());
const mockRemoveListener = vi.hoisted(() => vi.fn());
const mockParams = vi.hoisted(() => ({ id: 'case-1' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());

// ---------------------------------------------------------------------------
// Module-level mocks
// ---------------------------------------------------------------------------

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => mockParams,
    Outlet: () => <div id="outlet" />,
    useLocation: vi.fn(() => ({ pathname: '/', search: '' })),
    useNavigate: () => vi.fn()
  };
});

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: vi.fn(),
        put: vi.fn()
      }
    }
  }
}));

vi.mock('./detail/CaseDetails', () => ({
  default: () => <div id="case-details" />
}));

vi.mock('./detail/CaseSidebar', () => ({
  default: () => <div id="case-sidebar" />
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import CaseViewer from './CaseViewer';

// ---------------------------------------------------------------------------
// Provider wrapper – uses the real SocketContext so both CaseViewer and its
// useCase hook share the same context value provided here.
// ---------------------------------------------------------------------------

const createWrapper = () => {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <SocketContext.Provider
      value={
        {
          emit: mockEmit,
          open: mockOpen.current,
          fetchViewers: mockFetchViewers,
          addListener: mockAddListener,
          removeListener: mockRemoveListener,
          status: 1,
          reconnect: vi.fn(),
          viewers: {}
        } as any
      }
    >
      {children}
    </SocketContext.Provider>
  );
  return Wrapper;
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockEmit.mockClear();
  mockOpen.current = true;
  mockFetchViewers.mockClear().mockResolvedValue(undefined);
  mockAddListener.mockClear();
  mockRemoveListener.mockClear();
  mockDispatchApi.mockReset().mockResolvedValue(createMockCase({ case_id: 'case-1' }));
  mockParams.id = 'case-1';
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseViewer', () => {
  it('fetches viewers on mount', async () => {
    render(<CaseViewer />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockFetchViewers).toHaveBeenCalledWith('case-1');
    });
  });

  it('emits viewing action when socket is open', async () => {
    render(<CaseViewer />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockEmit).toHaveBeenCalledWith({
        broadcast: false,
        action: 'viewing',
        id: 'case-1'
      });
    });
  });

  it('emits stop_viewing on unmount', async () => {
    const { unmount } = render(<CaseViewer />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockEmit).toHaveBeenCalledWith({
        broadcast: false,
        action: 'viewing',
        id: 'case-1'
      });
    });

    mockEmit.mockClear();
    unmount();

    expect(mockEmit).toHaveBeenCalledWith({
      broadcast: false,
      action: 'stop_viewing',
      id: 'case-1'
    });
  });

  it('does not emit viewing when socket is closed', async () => {
    mockOpen.current = false;

    render(<CaseViewer />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockFetchViewers).toHaveBeenCalledWith('case-1');
    });

    expect(mockEmit).not.toHaveBeenCalled();
  });

  it('still fetches viewers when socket is closed', async () => {
    mockOpen.current = false;

    render(<CaseViewer />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockFetchViewers).toHaveBeenCalledWith('case-1');
    });
  });
});
