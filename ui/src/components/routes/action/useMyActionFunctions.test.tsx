/// <reference types="vitest" />
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowErrorMessage = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockShowInfoMessage = vi.hoisted(() => vi.fn(() => 'snackbar-key'));
const mockCloseSnackbar = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSearchActionPost = vi.hoisted(() => vi.fn());
const mockSearchHitPost = vi.hoisted(() => vi.fn((body: any) => body));
const mockActionPut = vi.hoisted(() => vi.fn((id: string, body: any) => ({ id, ...body })));
const mockActionPost = vi.hoisted(() => vi.fn((body: any) => body));
const mockActionExecutePost = vi.hoisted(() => vi.fn((body: any) => body));
const mockActionDelete = vi.hoisted(() => vi.fn((id: string, refresh?: string) => ({ id, refresh })));
const socketContextToken = vi.hoisted(() => ({ name: 'socket-context' }));

let paramsValue: any = {};
let locationValue: any = { pathname: '/action' };
let socketHandler: any;
const mockAddListener = vi.fn((_: string, handler: any) => {
  socketHandler = handler;
});
const mockRemoveListener = vi.fn();

vi.mock('@mui/icons-material', () => ({
  Terminal: () => <div>terminal</div>
}));

vi.mock('@mui/material', () => ({
  LinearProgress: () => <div>progress</div>,
  Stack: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: mockSearchHitPost
      },
      action: {
        post: mockSearchActionPost
      }
    },
    action: {
      put: mockActionPut,
      post: mockActionPost,
      del: mockActionDelete,
      execute: {
        post: mockActionExecutePost
      }
    }
  }
}));

vi.mock('components/app/providers/SocketProvider', () => ({
  SocketContext: socketContextToken
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({
    showErrorMessage: mockShowErrorMessage,
    showSuccessMessage: mockShowSuccessMessage,
    showInfoMessage: mockShowInfoMessage
  })
}));

vi.mock('notistack', () => ({
  useSnackbar: () => ({ closeSnackbar: mockCloseSnackbar })
}));

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey, values }: any) => <span>{`${i18nKey}:${values?.action ?? values?.messages ?? values?.message ?? ''}`}</span>,
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue,
  useNavigate: () => mockNavigate,
  useParams: () => paramsValue
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === socketContextToken) {
        return { addListener: mockAddListener, removeListener: mockRemoveListener };
      }
      return actual.useContext(context);
    }
  };
});

vi.mock('uuid', () => ({
  v4: () => 'req-123'
}));

import useMyActionFunctions from './useMyActionFunctions';

describe('useMyActionFunctions', () => {
  beforeEach(() => {
    paramsValue = {};
    locationValue = { pathname: '/action' };
    socketHandler = undefined;
    mockDispatchApi.mockReset();
    mockShowErrorMessage.mockReset();
    mockShowSuccessMessage.mockReset();
    mockShowInfoMessage.mockReset();
    mockShowInfoMessage.mockReturnValue('snackbar-key');
    mockCloseSnackbar.mockReset();
    mockNavigate.mockReset();
    mockSearchActionPost.mockReset();
    mockSearchHitPost.mockClear();
    mockActionPut.mockClear();
    mockActionPost.mockClear();
    mockActionExecutePost.mockClear();
    mockActionDelete.mockClear();
    mockAddListener.mockClear();
    mockRemoveListener.mockClear();
  });

  it('searches and saves both new and existing actions', async () => {
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request?.track_total_hits) return { items: [{ howler: { id: 'h1' } }], total: 1 };
      if (request?.name === 'New Action') return { action_id: 'action-1' };
      if (request?.id === 'existing-id') return { updated: true };
      return {};
    });

    const { result, unmount } = renderHook(() => useMyActionFunctions());

    await act(async () => {
      await result.current.onSearch('howler.id:*');
    });
    expect(result.current.responseQuery).toBe('howler.id:*');
    expect(result.current.response?.total).toBe(1);

    await act(async () => {
      await result.current.saveAction('', '', [], []);
    });
    expect(mockShowErrorMessage).toHaveBeenCalledWith('route.actions.query.empty');

    await act(async () => {
      await result.current.saveAction('New Action', 'status:open', [], ['manual']);
    });
    expect(mockActionPost).toHaveBeenCalledWith({
      name: 'New Action',
      query: 'status:open',
      operations: [],
      triggers: ['manual']
    });
    expect(mockNavigate).toHaveBeenCalledWith('/action/action-1');

    paramsValue = { id: 'existing-id' };
    unmount();
    const updatedHook = renderHook(() => useMyActionFunctions());
    await act(async () => {
      await updatedHook.result.current.saveAction('Existing', 'status:closed', [], []);
    });
    expect(mockActionPut).toHaveBeenCalledWith('existing-id', {
      name: 'Existing',
      query: 'status:closed',
      operations: []
    });
    expect(mockNavigate).toHaveBeenCalledWith('/action/existing-id');
  });

  it('submits actions, tracks socket progress, and deletes detailed actions', async () => {
    locationValue = { pathname: '/action/action-9' };
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request?.request_id && Array.isArray(request?.operations)) {
        return { phase: [{ outcome: 'success', message: 'done' }] };
      }
      if (request?.track_total_hits) {
        return { items: [{ howler: { id: 'h2' } }], total: 1 };
      }
      if (request?.id === 'action-9') return {};
      return {};
    });

    const { result } = renderHook(() => useMyActionFunctions());

    expect(mockAddListener).toHaveBeenCalledWith('action', expect.any(Function));

    await act(async () => {
      socketHandler?.({ type: 'action', request_id: 'req-123', processed: 2, total: 5 });
    });
    expect(result.current.progress).toEqual([0, 0]);

    await act(async () => {
      await result.current.submitAction('status:open', [{ id: 'op' }] as any);
    });
    expect(mockActionExecutePost).toHaveBeenCalledWith({
      request_id: 'req-123',
      query: 'status:open',
      operations: [{ id: 'op' }]
    });
    await waitFor(() => expect(result.current.report).toEqual({ phase: [{ outcome: 'success', message: 'done' }] }));
    expect(result.current.responseQuery).toBe('status:open');

    await act(async () => {
      await result.current.deleteAction('action-9');
    });
    expect(mockActionDelete).toHaveBeenCalledWith('action-9', 'wait_for');
    expect(mockNavigate).toHaveBeenCalledWith('/action');
  });

  it('executes an action and reports mixed outcomes', async () => {
    mockSearchActionPost.mockResolvedValueOnce({ items: [{ name: 'Demo Action' }] });
    mockDispatchApi.mockResolvedValueOnce({
      stage: [
        { outcome: 'error', message: 'broken' },
        { outcome: 'skipped', message: 'ignored' },
        { outcome: 'success', message: 'done' }
      ]
    });

    const { result } = renderHook(() => useMyActionFunctions());

    await act(async () => {
      await result.current.executeAction('action-1', 'status:open');
    });

    expect(mockShowInfoMessage).toHaveBeenCalled();
    expect(mockShowErrorMessage).toHaveBeenCalled();
    expect(mockShowSuccessMessage).toHaveBeenCalled();
    expect(mockCloseSnackbar).toHaveBeenCalledWith('snackbar-key');
    expect(result.current.report).toEqual({
      stage: [
        { outcome: 'error', message: 'broken' },
        { outcome: 'skipped', message: 'ignored' },
        { outcome: 'success', message: 'done' }
      ]
    });
  });
});
