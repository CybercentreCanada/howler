/// <reference types="vitest" />
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockState = vi.hoisted(() => ({
  listResponse: { items: [] as any[], offset: 0, rows: 20, has_more: false },
  nextPage: { items: [] as any[], offset: 20, rows: 20, has_more: false },
  run: undefined as any
}));
const mockAuthSession = vi.hoisted(() => ({ token: 'session-a' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const socketToken = vi.hoisted(() => ({ name: 'socket-context' }));
const socketHandlers = vi.hoisted(() => new Map<string, (data: any) => void>());
const mockAddListener = vi.hoisted(() =>
  vi.fn((key: string, handler: (data: any) => void) => socketHandlers.set(key, handler))
);
const mockRemoveListener = vi.hoisted(() => vi.fn((key: string) => socketHandlers.delete(key)));

vi.mock('@mui/icons-material', () => ({
  ExpandMore: () => <span>expand</span>,
  Refresh: () => <span>refresh</span>,
  PsychologyAlt: () => null,
  LocalPolice: () => null,
  MoodBad: () => null,
  NewReleases: () => null,
  Star: () => null,
  Timeline: () => null
}));

vi.mock('@mui/material', () => ({
  Accordion: ({ children, expanded, onChange }: any) => {
    const [summary, details] = Array.isArray(children) ? children : [children, null];
    return (
      <div>
        <button aria-expanded={expanded} onClick={event => onChange?.(event, !expanded)}>
          {summary}
        </button>
        {expanded && details}
      </div>
    );
  },
  AccordionDetails: ({ children }: any) => <div>{children}</div>,
  AccordionSummary: ({ children }: any) => <span>{children}</span>,
  Alert: ({ children }: any) => <div>{children}</div>,
  Button: ({ children, onClick, disabled }: any) => (
    <button disabled={disabled} onClick={onClick}>
      {children}
    </button>
  ),
  Chip: ({ label }: any) => <span>{label}</span>,
  CircularProgress: () => <span>refreshing</span>,
  IconButton: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
  LinearProgress: () => <div>loading-runs</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <span>{children}</span>
}));

vi.mock('api', () => ({
  default: {
    action: {
      runs: {
        list: (query: any) => ({ kind: 'list', query }),
        get: (runId: string) => ({ kind: 'detail', runId })
      }
    }
  }
}));

vi.mock('components/app/providers/SocketProvider', () => ({
  SocketContext: socketToken
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  default: () => ({ get: () => mockAuthSession.token })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, values?: any) =>
      values?.count !== undefined ? `${key}:${values.count}` : values?.runId ? `${key}:${values.runId}` : key
  })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) =>
      context === socketToken
        ? { addListener: mockAddListener, removeListener: mockRemoveListener }
        : actual.useContext(context)
  };
});

import ActionRunHistory from './ActionRunHistory';

const summary = (revision = 1, state = 'completed', runId = 'run-1') => ({
  run_id: runId,
  operation_id: 'ai_triage',
  request_id: 'request-1',
  action_id: 'action-1',
  trigger: null,
  state,
  revision,
  created_at: '2026-10-01T00:00:00Z',
  started_at: '2026-10-01T00:00:01Z',
  updated_at: '2026-10-01T00:00:02Z',
  finished_at: '2026-10-01T00:00:02Z',
  expires_at: null,
  counts: { total: 2, queued: 0, running: 0, succeeded: 1, failed: 1, skipped: 0 }
});

const detail = (revision = 1, state = 'completed', runId = 'run-1') => ({
  ...summary(revision, state, runId),
  results: [
    {
      hit_id: 'hit-1',
      state: 'failed',
      attempts: 2,
      reason: 'The model response was invalid',
      message: 'No lead was created',
      started_at: '2026-10-01T00:00:01Z',
      finished_at: '2026-10-01T00:00:02Z'
    }
  ]
});

const apiError = (statusCode: number) =>
  Object.assign(new Error(`HTTP ${statusCode}`), { cause: { api_status_code: statusCode } });

describe('ActionRunHistory', () => {
  beforeEach(() => {
    socketHandlers.clear();
    mockAddListener.mockClear();
    mockRemoveListener.mockClear();
    mockDispatchApi.mockReset();
    mockAuthSession.token = 'session-a';
    mockState.listResponse = { items: [summary()], offset: 0, rows: 20, has_more: false };
    mockState.nextPage = { items: [], offset: 20, rows: 20, has_more: false };
    mockState.run = detail();
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request.kind === 'list') {
        return request.query.offset > 0 ? mockState.nextPage : mockState.listResponse;
      }
      if (mockState.run instanceof Error) {
        throw mockState.run;
      }
      return mockState.run;
    });
  });

  it('reloads persisted history and shows per-hit partial failures and reasons', async () => {
    render(<ActionRunHistory actionId="action-1" />);

    const runRow = await screen.findByRole('button', { name: /run-1/ });
    expect(mockDispatchApi).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'list',
        query: expect.objectContaining({ operation_id: 'ai_triage', action_id: 'action-1', rows: 20 })
      }),
      { throwError: true, showError: false }
    );
    expect(screen.getByText(/route\.actions\.run\.count\.failed:1/)).toBeInTheDocument();

    fireEvent.click(runRow);
    expect(await screen.findByText('The model response was invalid')).toBeInTheDocument();
    expect(screen.getByText('No lead was created')).toBeInTheDocument();
    expect(screen.getByText('route.actions.run.attempts:2')).toBeInTheDocument();
  });

  it('refetches owner-filtered REST state for socket revisions and isolates listener instances', async () => {
    const { unmount } = render(
      <>
        <ActionRunHistory actionId="action-1" />
        <ActionRunHistory actionId="action-1" />
      </>
    );

    await screen.findAllByText(/run-1/);
    const listenerKeys = mockAddListener.mock.calls.map(([key]) => key);
    expect(new Set(listenerKeys).size).toBe(2);
    expect(listenerKeys.every(key => key.startsWith('ai-triage-runs-'))).toBe(true);

    fireEvent.click(screen.getAllByRole('button', { name: /run-1/ })[0]!);
    expect(await screen.findByText('The model response was invalid')).toBeInTheDocument();

    mockState.listResponse = { ...mockState.listResponse, items: [summary(2, 'running')] };
    mockState.run = detail(2, 'running');
    const event = {
      type: 'action',
      operation_id: 'ai_triage',
      run_id: 'run-1',
      request_id: 'request-1',
      revision: 2,
      state: 'running',
      processed: 1,
      total: 2,
      error: false,
      message: '',
      status: 200
    };
    act(() => socketHandlers.get(listenerKeys[0]!)?.(event));

    await waitFor(() => {
      expect(mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'list').length).toBeGreaterThanOrEqual(
        3
      );
      expect(mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'detail').length).toBeGreaterThanOrEqual(
        2
      );
    });

    unmount();
    expect(mockRemoveListener).toHaveBeenCalledWith(listenerKeys[0]);
    expect(mockRemoveListener).toHaveBeenCalledWith(listenerKeys[1]);
  });

  it('clears selected details when a run becomes unavailable', async () => {
    render(<ActionRunHistory actionId="action-1" />);
    fireEvent.click(await screen.findByRole('button', { name: /run-1/ }));
    expect(await screen.findByText('The model response was invalid')).toBeInTheDocument();

    mockState.run = apiError(404);
    mockState.listResponse = { items: [], offset: 0, rows: 20, has_more: false };
    const listener = mockAddListener.mock.calls[0]?.[1];
    act(() =>
      listener?.({
        type: 'action',
        operation_id: 'ai_triage',
        run_id: 'run-1',
        request_id: 'request-1',
        revision: 2,
        state: 'completed',
        processed: 2,
        total: 2,
        error: false,
        message: '',
        status: 200
      })
    );

    await waitFor(() => expect(screen.queryByText('The model response was invalid')).not.toBeInTheDocument());
    expect(screen.queryByText('run-1')).not.toBeInTheDocument();
  });

  it('loads older persisted runs from the next page', async () => {
    mockState.listResponse = { items: [summary()], offset: 0, rows: 20, has_more: true };
    mockState.nextPage = { items: [summary(1, 'completed', 'run-2')], offset: 20, rows: 20, has_more: false };
    render(<ActionRunHistory />);

    await screen.findByRole('button', { name: /run-1/ });
    fireEvent.click(screen.getByRole('button', { name: 'route.actions.run.loadMore' }));

    expect(await screen.findByRole('button', { name: /run-2/ })).toBeInTheDocument();
    expect(mockDispatchApi).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'list', query: expect.objectContaining({ offset: 20, rows: 20 }) }),
      { throwError: true, showError: false }
    );
  });

  it('polls the REST endpoint while a run is active when no socket event arrives', async () => {
    mockState.listResponse = { items: [summary(1, 'running')], offset: 0, rows: 20, has_more: false };
    const noPoll = () => {};
    let pollCallback = noPoll;
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation((handler: TimerHandler, delay?: number) => {
        if (delay === 3000 && typeof handler === 'function') {
          pollCallback = handler as () => void;
        }
        return 1;
      });
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
    const view = render(<ActionRunHistory actionId="action-1" />);

    try {
      await screen.findByText('route.actions.run.state.running');
      const listCalls = mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'list').length;
      await act(async () => {
        pollCallback();
        await Promise.resolve();
      });
      await waitFor(() => {
        expect(mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'list').length).toBeGreaterThan(
          listCalls
        );
      });
    } finally {
      view.unmount();
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    }
  });

  it('clears the previous session cache after same-account reauthentication', async () => {
    const view = render(<ActionRunHistory actionId="action-1" />);
    fireEvent.click(await screen.findByRole('button', { name: /run-1/ }));
    expect(await screen.findByText('The model response was invalid')).toBeInTheDocument();
    const initialListCalls = mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'list').length;

    mockAuthSession.token = 'session-b';
    mockState.listResponse = { items: [], offset: 0, rows: 20, has_more: false };
    view.rerender(<ActionRunHistory actionId="action-1" />);

    await screen.findByText('route.actions.run.empty');
    expect(screen.queryByText('The model response was invalid')).not.toBeInTheDocument();
    expect(mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'list').length).toBeGreaterThan(
      initialListCalls
    );
  });

  it('does not redisplay cached action A after an A-to-B-to-A route change', async () => {
    const view = render(<ActionRunHistory actionId="action-a" />);
    expect(await screen.findByRole('button', { name: /run-1/ })).toBeInTheDocument();

    mockDispatchApi.mockImplementation((request: any) => {
      if (request.kind === 'list' && request.query.action_id === 'action-b') {
        return new Promise(() => {});
      }
      return Promise.resolve({ items: [], offset: 0, rows: 20, has_more: false });
    });
    view.rerender(<ActionRunHistory actionId="action-b" />);
    view.rerender(<ActionRunHistory actionId="action-a" />);

    await screen.findByText('route.actions.run.empty');
    expect(screen.queryByText('run-1')).not.toBeInTheDocument();
  });

  it('retries a pending accepted run from empty history without a socket event', async () => {
    mockState.listResponse = { items: [], offset: 0, rows: 20, has_more: true };
    mockState.run = detail(1, 'completed', 'run-accepted');
    let detailCalls = 0;
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request.kind === 'list') {
        return mockState.listResponse;
      }
      detailCalls += 1;
      if (detailCalls === 1) {
        throw apiError(503);
      }
      return mockState.run;
    });
    const noPoll = () => {};
    let pollCallback = noPoll;
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation((handler: TimerHandler, delay?: number) => {
        if (delay === 3000 && typeof handler === 'function') {
          pollCallback = handler as () => void;
        }
        return 1;
      });
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
    const view = render(<ActionRunHistory actionId="action-1" acceptedRunIds={['run-accepted']} />);

    try {
      await screen.findByText('route.actions.run.empty');
      expect(screen.getByText('route.actions.run.accepted.pending')).toBeInTheDocument();
      expect(screen.getByText('route.actions.run.id:run-accepted')).toBeInTheDocument();
      await waitFor(() => expect(detailCalls).toBe(1));
      await waitFor(() => expect(pollCallback).not.toBe(noPoll));
      await act(async () => {
        pollCallback();
        await Promise.resolve();
      });
      expect(await screen.findByRole('button', { name: /run-accepted/ })).toBeInTheDocument();
      expect(detailCalls).toBeGreaterThan(1);
      await waitFor(() => expect(clearIntervalSpy).toHaveBeenCalled());
    } finally {
      view.unmount();
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    }
  });

  it('fetches an accepted completed run directly when it is beyond the first history page', async () => {
    mockState.listResponse = {
      items: Array.from({ length: 20 }, (_, index) => summary(1, 'completed', `recent-${index}`)),
      offset: 0,
      rows: 20,
      has_more: true
    };
    mockState.run = detail(2, 'completed', 'run-beyond-page');
    render(<ActionRunHistory actionId="action-1" acceptedRunIds={['run-beyond-page']} />);

    await waitFor(() => expect(mockDispatchApi.mock.calls.some(([request]) => request.kind === 'detail')).toBe(true));
    expect(await screen.findByRole('button', { name: /run-beyond-page/ })).toBeInTheDocument();
    expect(mockDispatchApi).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'detail', runId: 'run-beyond-page' }),
      { throwError: true, showError: false }
    );
    expect([...socketHandlers.values()]).toHaveLength(1);
  });

  it('preserves active rows and retries history after a transient REST failure', async () => {
    mockState.listResponse = { items: [summary(1, 'running')], offset: 0, rows: 20, has_more: false };
    let shouldFail = false;
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request.kind !== 'list') {
        return mockState.run;
      }
      if (shouldFail) {
        shouldFail = false;
        throw apiError(503);
      }
      return mockState.listResponse;
    });
    const noPoll = () => {};
    let pollCallback = noPoll;
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation((handler: TimerHandler, delay?: number) => {
        if (delay === 3000 && typeof handler === 'function') {
          pollCallback = handler as () => void;
        }
        return 1;
      });
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
    const view = render(<ActionRunHistory actionId="action-1" />);

    try {
      const runRow = await screen.findByRole('button', { name: /run-1/ });
      shouldFail = true;
      await act(async () => {
        pollCallback();
        await Promise.resolve();
      });
      expect(runRow).toBeInTheDocument();

      await act(async () => {
        pollCallback();
        await Promise.resolve();
      });
      expect(await screen.findByRole('button', { name: /run-1/ })).toBeInTheDocument();
    } finally {
      view.unmount();
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    }
  });

  it('directly refreshes an active row from an older page and stops polling at completion', async () => {
    mockState.listResponse = { items: [summary()], offset: 0, rows: 20, has_more: true };
    mockState.nextPage = { items: [summary(1, 'running', 'run-old')], offset: 20, rows: 20, has_more: false };
    let completeOlderRun = false;
    let olderRunDetailCalls = 0;
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request.kind === 'list') {
        return request.query.offset > 0 ? mockState.nextPage : mockState.listResponse;
      }
      olderRunDetailCalls += 1;
      return detail(completeOlderRun ? 2 : 1, completeOlderRun ? 'completed' : 'running', 'run-old');
    });
    const noPoll = () => {};
    let pollCallback = noPoll;
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation((handler: TimerHandler, delay?: number) => {
        if (delay === 3000 && typeof handler === 'function') {
          pollCallback = handler as () => void;
        }
        return 1;
      });
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
    const view = render(<ActionRunHistory actionId="action-1" />);

    try {
      await screen.findByRole('button', { name: /run-1/ });
      fireEvent.click(screen.getByRole('button', { name: 'route.actions.run.loadMore' }));
      expect(await screen.findByRole('button', { name: /run-old/ })).toHaveTextContent(
        'route.actions.run.state.running'
      );
      await waitFor(() => expect(pollCallback).not.toBe(noPoll));

      completeOlderRun = true;
      await act(async () => {
        pollCallback();
        await Promise.resolve();
      });

      await waitFor(() =>
        expect(screen.getByRole('button', { name: /run-old/ })).toHaveTextContent('route.actions.run.state.completed')
      );
      expect(olderRunDetailCalls).toBeGreaterThan(0);
      await waitFor(() => expect(clearIntervalSpy).toHaveBeenCalled());
    } finally {
      view.unmount();
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    }
  });

  it('retries transient detail failures instead of blacklisting the run', async () => {
    mockState.listResponse = { items: [summary(1, 'running')], offset: 0, rows: 20, has_more: false };
    let failDetail = true;
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request.kind === 'list') {
        return mockState.listResponse;
      }
      if (failDetail) {
        failDetail = false;
        throw apiError(503);
      }
      return mockState.run;
    });
    const noPoll = () => {};
    let pollCallback = noPoll;
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation((handler: TimerHandler, delay?: number) => {
        if (delay === 3000 && typeof handler === 'function') {
          pollCallback = handler as () => void;
        }
        return 1;
      });
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
    const view = render(<ActionRunHistory actionId="action-1" />);

    try {
      fireEvent.click(await screen.findByRole('button', { name: /run-1/ }));
      await waitFor(() => {
        expect(mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'detail')).toHaveLength(1);
      });
      expect(screen.queryByText('The model response was invalid')).not.toBeInTheDocument();
      await waitFor(() => expect(setIntervalSpy.mock.calls.some(([, delay]) => delay === 3000)).toBe(true));
      await waitFor(() => expect(pollCallback).not.toBe(noPoll));
      await act(async () => {
        pollCallback();
        await Promise.resolve();
      });
      await waitFor(() => {
        expect(mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'detail').length).toBeGreaterThan(1);
      });
      expect(await screen.findByText('The model response was invalid')).toBeInTheDocument();
    } finally {
      view.unmount();
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    }
  });

  it('directly refreshes an older active run outside page one and stops polling on completion', async () => {
    mockState.listResponse = { items: [summary()], offset: 0, rows: 20, has_more: true };
    mockState.nextPage = { items: [summary(1, 'running', 'run-old')], offset: 20, rows: 20, has_more: false };
    let isComplete = false;
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request.kind === 'list') {
        return request.query.offset > 0 ? mockState.nextPage : mockState.listResponse;
      }
      return detail(isComplete ? 2 : 1, isComplete ? 'completed' : 'running', 'run-old');
    });
    const noPoll = () => {};
    let pollCallback = noPoll;
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation((handler: TimerHandler, delay?: number) => {
        if (delay === 3000 && typeof handler === 'function') {
          pollCallback = handler as () => void;
        }
        return 1;
      });
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
    const view = render(<ActionRunHistory actionId="action-1" />);

    try {
      await screen.findByRole('button', { name: /run-1/ });
      fireEvent.click(screen.getByRole('button', { name: 'route.actions.run.loadMore' }));
      expect(await screen.findByRole('button', { name: /run-old/ })).toHaveTextContent(
        'route.actions.run.state.running'
      );
      await waitFor(() => expect(pollCallback).not.toBe(noPoll));

      isComplete = true;
      await act(async () => {
        pollCallback();
        await Promise.resolve();
      });

      await waitFor(() =>
        expect(screen.getByRole('button', { name: /run-old/ })).toHaveTextContent('route.actions.run.state.completed')
      );
      await waitFor(() => expect(clearIntervalSpy).toHaveBeenCalled());
      expect(mockDispatchApi.mock.calls.filter(([request]) => request.kind === 'detail').length).toBeGreaterThan(0);
    } finally {
      view.unmount();
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    }
  });

  it.each([401, 404, undefined])(
    'invalidates in-flight list generations when a detail response denies access (%s)',
    async statusCode => {
      const view = render(<ActionRunHistory actionId="action-1" />);
      await screen.findByRole('button', { name: /run-1/ });

      const noResolve = () => {};
      let resolveDelayedList: (value: any) => void = noResolve;
      let delayNextList = false;
      mockDispatchApi.mockImplementation((request: any) => {
        if (request.kind === 'list') {
          if (delayNextList) {
            delayNextList = false;
            return new Promise(resolve => {
              resolveDelayedList = resolve;
            });
          }
          return Promise.resolve(mockState.listResponse);
        }
        return statusCode === undefined ? Promise.resolve(undefined) : Promise.reject(apiError(statusCode));
      });

      try {
        delayNextList = true;
        fireEvent.click(screen.getByLabelText('route.actions.run.refresh'));
        await waitFor(() => expect(resolveDelayedList).not.toBe(noResolve));
        fireEvent.click(screen.getByRole('button', { name: /run-1/ }));
        await waitFor(() => expect(screen.queryByRole('button', { name: /run-1/ })).not.toBeInTheDocument());

        await act(async () => {
          resolveDelayedList({ items: [summary()], offset: 0, rows: 20, has_more: false });
          await Promise.resolve();
        });
        expect(screen.queryByRole('button', { name: /run-1/ })).not.toBeInTheDocument();
      } finally {
        view.unmount();
      }
    }
  );
});
