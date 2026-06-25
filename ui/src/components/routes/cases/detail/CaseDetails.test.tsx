/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import type { Case } from 'models/entities/generated/Case';
import { type FC, type PropsWithChildren } from 'react';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// ---------------------------------------------------------------------------
// Hoisted stubs
// ---------------------------------------------------------------------------

const mockUpdate = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockShowModal = vi.hoisted(() => vi.fn());

// ---------------------------------------------------------------------------
// Module mocks (registered before the dynamic import below)
// ---------------------------------------------------------------------------

vi.mock('../hooks/useCase', () => ({
  default: ({ case: c }: { case: Case }) => ({
    case: c,
    update: mockUpdate,
    loading: false,
    missing: false
  })
}));

vi.mock('components/app/providers/ModalProvider', async () => {
  const { createContext } = await import('react');
  return {
    ModalContext: createContext({
      showModal: mockShowModal,
      close: vi.fn(),
      setContent: vi.fn(),
      withConfirmDeleteModal: vi.fn()
    })
  };
});

vi.mock('components/elements/UserList', () => ({
  default: () => <div id="user-list" />
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: { userId: string }) => <div>{userId}</div>
}));

vi.mock('components/elements/display/icons/SocketBadge', () => ({
  default: () => <span />
}));

vi.mock('./aggregates/SourceAggregate', () => ({
  default: () => <span />
}));

vi.mock('../modals/ResolveModal', () => ({
  default: () => null
}));

// ---------------------------------------------------------------------------
// Shared provider config
// ---------------------------------------------------------------------------

const mockConfig = {
  lookups: {
    'howler.status': ['open', 'in-progress', 'on-hold', 'resolved'],
    'case.escalation': ['normal', 'focus', 'crisis'],
    'howler.escalation': ['miss', 'hit', 'alert', 'evidence']
  }
} as any;

const mockViewers: Record<string, string[]> = {};

const Wrapper: FC<PropsWithChildren> = ({ children }) => (
  <ApiConfigContext.Provider value={{ config: mockConfig, setConfig: vi.fn() }}>
    <SocketContext.Provider
      value={
        {
          emit: vi.fn(),
          open: true,
          fetchViewers: vi.fn(),
          addListener: vi.fn(),
          removeListener: vi.fn(),
          status: 1,
          reconnect: vi.fn(),
          viewers: { ...mockViewers }
        } as any
      }
    >
      {children}
    </SocketContext.Provider>
  </ApiConfigContext.Provider>
);

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

const { default: CaseDetails } = await import('./CaseDetails');

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseDetails', () => {
  let user: UserEvent;
  let testCase: Case;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
    mockUpdate.mockResolvedValue(undefined);
    testCase = createMockCase({ case_id: 'test-case-id', status: 'open', escalation: 'normal' }) as Case;
    Object.keys(mockViewers).forEach(k => delete mockViewers[k]);
  });

  it('renders a skeleton and no controls when the case is null', () => {
    render(<CaseDetails case={null as any} />, { wrapper: Wrapper });

    expect(document.querySelector('.MuiSkeleton-root')).toBeTruthy();
    expect(screen.queryByRole('combobox')).toBeNull();
  });

  it('renders the status label and current status value', () => {
    render(<CaseDetails case={testCase} />, { wrapper: Wrapper });

    expect(screen.getByText('page.cases.detail.status')).toBeInTheDocument();
    expect(screen.getByDisplayValue('open')).toBeInTheDocument();
  });

  it('renders the escalation label and current escalation value', () => {
    render(<CaseDetails case={testCase} />, { wrapper: Wrapper });

    expect(screen.getByText('page.cases.detail.escalation')).toBeInTheDocument();
    expect(screen.getByDisplayValue('hit')).toBeInTheDocument();
  });

  describe('status changes', () => {
    it('calls update with the new status when a non-resolved option is selected', async () => {
      render(<CaseDetails case={testCase} />, { wrapper: Wrapper });

      await user.click(screen.getByDisplayValue('open'));
      await user.click(await screen.findByRole('option', { name: 'in-progress' }));

      await waitFor(() => {
        expect(mockUpdate).toHaveBeenCalledWith({ status: 'in-progress' });
      });
    });

    it('opens the resolve modal instead of calling update when "resolved" is selected', async () => {
      render(<CaseDetails case={testCase} />, { wrapper: Wrapper });

      await user.click(screen.getByDisplayValue('open'));
      await user.click(await screen.findByRole('option', { name: 'resolved' }));

      expect(mockShowModal).toHaveBeenCalledOnce();
      expect(mockUpdate).not.toHaveBeenCalled();
    });
  });

  describe('escalation changes', () => {
    it('calls update with the new escalation when an option is selected', async () => {
      render(<CaseDetails case={testCase} />, { wrapper: Wrapper });

      await user.click(screen.getByDisplayValue('normal'));
      await user.click(await screen.findByRole('option', { name: 'focus' }));

      await waitFor(() => {
        expect(mockUpdate).toHaveBeenCalledWith({ escalation: 'focus' });
      });
    });
  });

  describe('viewers section', () => {
    it('hides the viewers section when no viewers are active', () => {
      render(<CaseDetails case={testCase} />, { wrapper: Wrapper });

      expect(screen.queryByText('page.cases.detail.viewers')).toBeNull();
    });

    it('shows the viewers section and renders viewer avatars when active viewers are present', () => {
      mockViewers['test-case-id'] = ['user-1', 'user-2'];
      render(<CaseDetails case={testCase} />, { wrapper: Wrapper });

      expect(screen.getByText('page.cases.detail.viewers')).toBeInTheDocument();
      expect(screen.getByText('user-1')).toBeInTheDocument();
      expect(screen.getByText('user-2')).toBeInTheDocument();
    });
  });
});
