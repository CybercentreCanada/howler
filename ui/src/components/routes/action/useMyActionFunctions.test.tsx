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
const mockAuthSession = vi.hoisted(() => ({ token: 'session-a' }));

let paramsValue: any = {};
let locationValue: any = { pathname: '/action' };

vi.mock('@mui/icons-material', () => ({
  Terminal: () => <div>terminal</div>,
  PsychologyAlt: () => null,
  LocalPolice: () => null,
  MoodBad: () => null,
  NewReleases: () => null,
  Star: () => null,
  Timeline: () => null
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

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  default: () => ({ get: () => mockAuthSession.token })
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
  Trans: ({ i18nKey, values }: any) => (
    <span>{`${i18nKey}:${values?.action ?? values?.messages ?? values?.message ?? ''}`}</span>
  ),
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue,
  useNavigate: () => mockNavigate,
  useParams: () => paramsValue
}));

vi.mock('uuid', () => ({
  v4: () => 'req-123'
}));

import useMyActionFunctions from './useMyActionFunctions';

describe('useMyActionFunctions', () => {
  beforeEach(() => {
    paramsValue = {};
    locationValue = { pathname: '/action' };
    mockAuthSession.token = 'session-a';
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

  it('submits actions and deletes detailed actions', async () => {
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

  it.each(['action route', 'auth session'] as const)(
    'clears prior action state and ignores a stale search when the %s changes',
    async contextChange => {
      paramsValue = { id: 'action-a' };
      locationValue = { pathname: '/action/action-a/edit' };
      mockDispatchApi
        .mockResolvedValueOnce({ items: [{ howler: { id: 'hit-a' } }], total: 1 })
        .mockResolvedValueOnce({ phase: [{ outcome: 'success', message: 'done' }] });
      mockSearchActionPost.mockResolvedValueOnce({ items: [{ name: 'Action A' }] });

      const { result, rerender } = renderHook(() => useMyActionFunctions());
      await act(async () => result.current.onSearch('status:a'));
      await act(async () => result.current.executeAction('action-a'));
      expect(result.current.responseQuery).toBe('status:a');
      expect(result.current.report).toEqual({ phase: [{ outcome: 'success', message: 'done' }] });

      const noResolve = () => {};
      let resolveStaleSearch: (value: any) => void = noResolve;
      mockDispatchApi.mockImplementationOnce(
        () =>
          new Promise(resolve => {
            resolveStaleSearch = resolve;
          })
      );
      let staleSearch: Promise<void> = Promise.resolve();
      act(() => {
        staleSearch = result.current.onSearch('status:old');
      });
      await waitFor(() => expect(resolveStaleSearch).not.toBe(noResolve));

      if (contextChange === 'action route') {
        paramsValue = { id: 'action-b' };
        locationValue = { pathname: '/action/action-b/edit' };
      } else {
        mockAuthSession.token = 'session-b';
      }
      rerender();

      expect(result.current.response).toBeUndefined();
      expect(result.current.responseQuery).toBe('');
      expect(result.current.report).toBeUndefined();
      expect(result.current.loading).toBe(false);

      if (contextChange === 'action route') {
        paramsValue = { id: 'action-a' };
        locationValue = { pathname: '/action/action-a/edit' };
      } else {
        mockAuthSession.token = 'session-a';
      }
      rerender();

      mockDispatchApi.mockResolvedValueOnce({ items: [{ howler: { id: 'hit-b' } }], total: 2 });
      await act(async () => result.current.onSearch('status:new'));
      resolveStaleSearch({ items: [{ howler: { id: 'stale-hit' } }], total: 9 });
      await act(async () => staleSearch);

      expect(result.current.response?.total).toBe(2);
      expect(result.current.responseQuery).toBe('status:new');
      expect(result.current.response?.items[0]?.howler?.id).toBe('hit-b');
    }
  );

  it('ignores an old execute result and its notifications after returning to the same action route', async () => {
    paramsValue = { id: 'action-a' };
    locationValue = { pathname: '/action/action-a' };
    mockSearchActionPost
      .mockResolvedValueOnce({ items: [{ name: 'Old execution' }] })
      .mockResolvedValueOnce({ items: [{ name: 'Current execution' }] });

    const noResolve = () => {};
    let resolveOldExecution: (value: any) => void = noResolve;
    mockDispatchApi.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          resolveOldExecution = resolve;
        })
    );

    const { result, rerender } = renderHook(() => useMyActionFunctions());
    let oldExecution: Promise<void> = Promise.resolve();
    act(() => {
      oldExecution = result.current.executeAction('action-a');
    });
    await waitFor(() => expect(resolveOldExecution).not.toBe(noResolve));

    paramsValue = { id: 'action-b' };
    locationValue = { pathname: '/action/action-b' };
    rerender();
    paramsValue = { id: 'action-a' };
    locationValue = { pathname: '/action/action-a' };
    rerender();

    const currentReport = { stage: [{ outcome: 'success', message: 'current success' }] };
    mockDispatchApi.mockResolvedValueOnce(currentReport);
    await act(async () => result.current.executeAction('action-a'));

    resolveOldExecution({ stage: [{ outcome: 'error', message: 'stale error' }] });
    await act(async () => oldExecution);

    expect(result.current.report).toEqual(currentReport);
    expect(mockShowErrorMessage).not.toHaveBeenCalled();
    expect(mockShowSuccessMessage).toHaveBeenCalledTimes(1);
  });

  it('does not let a save from an earlier visit navigate or clear current loading state', async () => {
    paramsValue = { id: 'action-a' };
    locationValue = { pathname: '/action/action-a/edit' };

    const noResolve = () => {};
    let resolveOldSave: (value: any) => void = noResolve;
    mockDispatchApi.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          resolveOldSave = resolve;
        })
    );

    const { result, rerender } = renderHook(() => useMyActionFunctions());
    let oldSave: Promise<void> = Promise.resolve();
    act(() => {
      oldSave = result.current.saveAction('Old A', 'status:old', [], []);
    });
    await waitFor(() => expect(resolveOldSave).not.toBe(noResolve));

    paramsValue = { id: 'action-b' };
    locationValue = { pathname: '/action/action-b/edit' };
    rerender();
    paramsValue = { id: 'action-a' };
    locationValue = { pathname: '/action/action-a/edit' };
    rerender();

    act(() => result.current.setLoading(true));
    resolveOldSave({ updated: true });
    await act(async () => oldSave);

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(true);
  });
});
