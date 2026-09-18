/// <reference types="vitest" />
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowWarningMessage = vi.hoisted(() => vi.fn());
const mockUpdateRecord = vi.hoisted(() => vi.fn());
const mockDrawerOpen = vi.hoisted(() => vi.fn());
const mockDrawerClose = vi.hoisted(() => vi.fn());
const mockShowModal = vi.hoisted(() => vi.fn());
const mockTransitionPost = vi.hoisted(() => vi.fn());
const mockHitGet = vi.hoisted(() => vi.fn());
const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const appDrawerContextToken = vi.hoisted(() => ({ name: 'drawer-context' }));
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));

let configValue: any = {
  config: {
    lookups: {
      transitions: {
        open: ['assign_to_me', 'assign_to_other', 'promote'],
        'in-progress': ['release', 'pause', 'demote']
      }
    }
  }
};

vi.mock('@tui/core', () => ({
  useAppUser: () => ({
    user: { username: 'alice', email: 'alice@example.com' }
  })
}));

vi.mock('api', () => ({
  default: {
    hit: {
      transition: { post: mockTransitionPost },
      get: mockHitGet
    }
  }
}));

vi.mock('components/app/drawers/AssignUserDrawer', () => ({
  default: ({ onAssigned }: any) => <button onClick={() => onAssigned('bob')}>assign-user</button>
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/AppDrawerProvider', () => ({
  AppDrawerContext: appDrawerContextToken
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/elements/display/modals/RationaleModal', () => ({
  default: ({ onSubmit }: any) => <button onClick={() => onSubmit('modal rationale')}>submit-rationale</button>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showWarningMessage: mockShowWarningMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string, vars?: any) => (vars?.assessment ? `${key}:${vars.assessment}` : key) })
}));

vi.mock('use-context-selector', async importOriginal => {
  const actual = await importOriginal<typeof import('use-context-selector')>();
  return {
    ...actual,
    useContextSelector: (_context: any, selector: (ctx: any) => any) => selector({ updateRecord: mockUpdateRecord })
  };
});

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return configValue;
      if (context === appDrawerContextToken) return { open: mockDrawerOpen, close: mockDrawerClose };
      if (context === modalContextToken) return { showModal: mockShowModal };
      return actual.useContext(context);
    }
  };
});

import useHitActions from './useHitActions';

describe('useHitActions', () => {
  beforeEach(() => {
    configValue = {
      config: {
        lookups: {
          transitions: {
            open: ['assign_to_me', 'assign_to_other', 'promote'],
            'in-progress': ['release', 'pause', 'demote']
          }
        }
      }
    };
    mockDispatchApi.mockReset();
    mockShowWarningMessage.mockReset();
    mockUpdateRecord.mockReset();
    mockDrawerOpen.mockReset();
    mockDrawerClose.mockReset();
    mockShowModal.mockReset();
    mockTransitionPost.mockReset();
    mockHitGet.mockReset();
  });

  it('computes voting and transition state for a single hit', () => {
    const hit = {
      howler: {
        id: 'hit-1',
        status: 'open',
        assignment: 'bob',
        escalation: 'hit',
        votes: { benign: ['alice@example.com'] }
      }
    } as any;

    const { result } = renderHook(() => useHitActions(hit));

    expect(result.current.canVote).toBe(true);
    expect(result.current.canAssess).toBe(true);
    expect(result.current.selectedVote).toBe('benign');
    expect(result.current.availableTransitions.map(v => v.name)).toEqual(['assign_to_other', 'assign_to_me', 'promote']);
  });

  it('votes and updates hits, including conflict recovery', async () => {
    const hit = { howler: { id: 'hit-1', status: 'open', assignment: 'bob', escalation: 'hit', votes: {} } } as any;
    mockTransitionPost.mockImplementation((id: string, body: any) => ({ id, body }));
    mockDispatchApi.mockImplementationOnce(async (_req, opts) => {
      await opts.onConflict();
      return { howler: { id: 'hit-1', vote: 'malicious' } };
    });
    mockHitGet.mockResolvedValueOnce({ howler: { id: 'hit-1', refreshed: true } });
    mockTransitionPost.mockResolvedValueOnce({ howler: { id: 'hit-1', vote: 'malicious' } });

    const { result } = renderHook(() => useHitActions(hit));
    await act(async () => {
      await result.current.vote('malicious');
    });

    expect(mockHitGet).toHaveBeenCalledWith('hit-1');
    expect(mockUpdateRecord).toHaveBeenCalledWith({ howler: { id: 'hit-1', vote: 'malicious' } });
  });

  it('assesses hits with modal rationale and warns on conflicting server updates', async () => {
    const hit = { howler: { id: 'hit-2', status: 'open', assignment: 'bob', assessment: null, escalation: 'hit' } } as any;
    mockTransitionPost.mockImplementation((id: string, body: any) => ({ id, body }));
    mockShowModal.mockImplementation((node: any) => node.props.onSubmit('modal rationale'));
    mockDispatchApi.mockImplementationOnce(async (_req, opts) => {
      await opts.onConflict();
      return null;
    });
    mockHitGet.mockResolvedValueOnce({ howler: { id: 'hit-2', assessment: 'existing' } });

    const { result } = renderHook(() => useHitActions(hit));
    await act(async () => {
      await result.current.assess('malicious');
    });

    expect(mockUpdateRecord).toHaveBeenCalledWith({ howler: { id: 'hit-2', assessment: 'existing' } });
    expect(mockShowWarningMessage).toHaveBeenCalledWith('hit.actions.conflict.assess');
  });

  it('uses provided rationale and manages assignment workflows', async () => {
    const hit = { howler: { id: 'hit-3', status: 'open', assignment: 'bob', assessment: null, escalation: 'alert' } } as any;
    mockTransitionPost.mockImplementation((id: string, body: any) => ({ id, body }));
    mockDispatchApi.mockResolvedValue({ howler: { id: 'hit-3', updated: true } });
    mockDrawerOpen.mockImplementation((props: any) => props.children.props.onAssigned('bob'));

    const { result } = renderHook(() => useHitActions(hit));

    await act(async () => {
      await result.current.assess('benign', true, 'manual rationale');
    });
    expect(mockTransitionPost).toHaveBeenCalledWith('hit-3', {
      transition: 'assess',
      data: { assessment: 'benign', rationale: 'manual rationale' }
    });

    await act(async () => {
      await result.current.manage('assign_to_other');
    });
    expect(mockDrawerOpen).toHaveBeenCalled();
    expect(mockTransitionPost).toHaveBeenCalledWith('hit-3', {
      transition: 'assign_to_other',
      data: { assignee: 'bob' }
    });
  });
});
