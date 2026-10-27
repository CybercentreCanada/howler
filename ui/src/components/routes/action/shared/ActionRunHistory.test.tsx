/// <reference types="vitest" />
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({
  list: { items: [] as any[], offset: 0, rows: 20, has_more: false },
  page: { items: [] as any[], offset: 20, rows: 20, has_more: false },
  detail: undefined as any
}));
const auth = vi.hoisted(() => ({ token: 'session-a' }));
const dispatch = vi.hoisted(() => vi.fn());
const socketToken = vi.hoisted(() => ({ name: 'socket-context' }));
const handlers = vi.hoisted(() => new Map<string, (data: any) => void>());
const addListener = vi.hoisted(() => vi.fn((key: string, handler: (data: any) => void) => handlers.set(key, handler)));
const removeListener = vi.hoisted(() => vi.fn((key: string) => handlers.delete(key)));

vi.mock('@mui/icons-material', () => ({
  ExpandMore: () => null,
  Refresh: () => null,
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
  CircularProgress: () => <span>busy</span>,
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
vi.mock('components/app/providers/SocketProvider', () => ({ SocketContext: socketToken }));
vi.mock('components/hooks/useMyApi', () => ({ default: () => ({ dispatchApi: dispatch }) }));
vi.mock('components/hooks/useMyLocalStorage', () => ({ default: () => ({ get: () => auth.token }) }));
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
      context === socketToken ? { addListener, removeListener } : actual.useContext(context)
  };
});

import ActionRunHistory from './ActionRunHistory';

const summary = (runId = 'run-1', runState = 'completed') => ({
  run_id: runId,
  operation_id: 'ai_triage',
  request_id: 'request-1',
  action_id: 'action-1',
  trigger: null,
  state: runState,
  revision: 1,
  created_at: '2026-10-01T00:00:00Z',
  started_at: null,
  updated_at: '2026-10-01T00:00:02Z',
  finished_at: null,
  expires_at: null,
  counts: { total: 2, queued: 0, running: 0, succeeded: 1, failed: 1, skipped: 0 }
});
const runDetails = (runId = 'run-1') => ({
  ...summary(runId),
  results: [
    { hit_id: 'hit-1', state: 'failed', attempts: 2, reason: 'Invalid model response', message: 'No lead created' }
  ]
});
const apiError = (status: number) => Object.assign(new Error(`HTTP ${status}`), { cause: { api_status_code: status } });
const watchPolling = () => {
  const noPoll = () => {};
  let poll = noPoll;
  const set = vi.spyOn(window, 'setInterval').mockImplementation((handler: TimerHandler, delay?: number) => {
    if (delay === 3000 && typeof handler === 'function') poll = handler as () => void;
    return 1;
  });
  const clear = vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
  return { noPoll, getPoll: () => poll, set, clear };
};

describe('ActionRunHistory', () => {
  beforeEach(() => {
    handlers.clear();
    addListener.mockClear();
    removeListener.mockClear();
    dispatch.mockReset();
    auth.token = 'session-a';
    state.list = { items: [summary()], offset: 0, rows: 20, has_more: false };
    state.page = { items: [], offset: 20, rows: 20, has_more: false };
    state.detail = runDetails();
    dispatch.mockImplementation(async (request: any) => {
      if (request.kind === 'list') return request.query.offset ? state.page : state.list;
      if (state.detail instanceof Error) throw state.detail;
      return state.detail;
    });
  });

  it('loads the list and renders expanded per-hit details', async () => {
    render(<ActionRunHistory actionId="action-1" />);
    const row = await screen.findByRole('button', { name: /run-1/ });
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'list',
        query: expect.objectContaining({
          operation_id: 'ai_triage',
          action_id: 'action-1',
          offset: 0,
          rows: 20
        })
      }),
      { throwError: true, showError: false }
    );
    expect(row).toHaveTextContent('route.actions.run.count.failed:1');
    fireEvent.click(row);
    expect(await screen.findByText('Invalid model response')).toBeInTheDocument();
    expect(screen.getByText('No lead created')).toBeInTheDocument();
  });

  it('paginates older runs', async () => {
    state.list.has_more = true;
    state.page = { items: [summary('run-2')], offset: 20, rows: 20, has_more: false };
    render(<ActionRunHistory />);
    await screen.findByRole('button', { name: /run-1/ });
    fireEvent.click(screen.getByRole('button', { name: 'route.actions.run.loadMore' }));
    expect(await screen.findByRole('button', { name: /run-2/ })).toBeInTheDocument();
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'list', query: expect.objectContaining({ offset: 20 }) }),
      { throwError: true, showError: false }
    );
  });

  it('refreshes list and selected details on matching action socket events', async () => {
    render(<ActionRunHistory requestId="request-1" />);
    fireEvent.click(await screen.findByRole('button', { name: /run-1/ }));
    expect(await screen.findByText('Invalid model response')).toBeInTheDocument();
    state.list = { ...state.list, items: [summary('run-1', 'running')] };
    state.detail = { ...runDetails(), state: 'running' };
    const listener = [...handlers.values()][0]!;
    const listCalls = dispatch.mock.calls.filter(([request]) => request.kind === 'list').length;
    act(() => listener({ type: 'action', operation_id: 'ai_triage', run_id: 'run-1', request_id: 'request-1' }));
    await waitFor(() => {
      expect(dispatch.mock.calls.filter(([request]) => request.kind === 'list').length).toBeGreaterThan(listCalls);
      expect(dispatch.mock.calls.filter(([request]) => request.kind === 'detail').length).toBeGreaterThan(1);
      expect(screen.getByRole('button', { name: /run-1/ })).toHaveTextContent('route.actions.run.state.running');
    });
  });

  it('polls active runs every three seconds and stops when complete', async () => {
    state.list = { ...state.list, items: [summary('run-1', 'running')] };
    const polling = watchPolling();
    const view = render(<ActionRunHistory />);
    try {
      await screen.findByText('route.actions.run.state.running');
      expect(polling.set).toHaveBeenCalledWith(expect.any(Function), 3000);
      const calls = dispatch.mock.calls.filter(([request]) => request.kind === 'list').length;
      state.list = { ...state.list, items: [summary()] };
      await act(async () => {
        polling.getPoll()();
        await Promise.resolve();
      });
      await waitFor(() => {
        expect(dispatch.mock.calls.filter(([request]) => request.kind === 'list').length).toBeGreaterThan(calls);
        expect(screen.getByRole('button', { name: /run-1/ })).toHaveTextContent('route.actions.run.state.completed');
        expect(polling.clear).toHaveBeenCalled();
      });
    } finally {
      view.unmount();
      polling.set.mockRestore();
      polling.clear.mockRestore();
    }
  });

  it('keeps accepted IDs pending until a poll finds the run', async () => {
    state.list = { items: [], offset: 0, rows: 20, has_more: false };
    const polling = watchPolling();
    const view = render(<ActionRunHistory acceptedRunIds={['run-new']} />);
    try {
      expect(await screen.findByText('route.actions.run.accepted.pending')).toBeInTheDocument();
      expect(screen.getByText('route.actions.run.id:run-new')).toBeInTheDocument();
      await waitFor(() => expect(polling.getPoll()).not.toBe(polling.noPoll));
      state.list = { ...state.list, items: [summary('run-new', 'running')] };
      await act(async () => {
        polling.getPoll()();
        await Promise.resolve();
      });
      expect(await screen.findByRole('button', { name: /run-new/ })).toBeInTheDocument();
      expect(screen.queryByText('route.actions.run.accepted.pending')).not.toBeInTheDocument();
    } finally {
      view.unmount();
      polling.set.mockRestore();
      polling.clear.mockRestore();
    }
  });

  it('preserves expanded history when accepted IDs change', async () => {
    state.list.has_more = true;
    state.page = { items: [summary('run-old')], offset: 20, rows: 20, has_more: false };
    state.detail = runDetails('run-old');
    const view = render(<ActionRunHistory acceptedRunIds={[]} />);
    await screen.findByRole('button', { name: /run-1/ });
    fireEvent.click(screen.getByRole('button', { name: 'route.actions.run.loadMore' }));
    fireEvent.click(await screen.findByRole('button', { name: /run-old/ }));
    expect(await screen.findByText('Invalid model response')).toBeInTheDocument();
    const listenerCount = addListener.mock.calls.length;
    view.rerender(<ActionRunHistory acceptedRunIds={['run-new']} />);
    expect(await screen.findByRole('button', { name: /run-old/ })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Invalid model response')).toBeInTheDocument();
    expect(addListener).toHaveBeenCalledTimes(listenerCount);
    expect(removeListener).not.toHaveBeenCalled();
  });

  it('isolates history when the action route or auth session changes', async () => {
    const view = render(<ActionRunHistory actionId="action-a" />);
    await screen.findByRole('button', { name: /run-1/ });
    state.list = { items: [], offset: 0, rows: 20, has_more: false };
    view.rerender(<ActionRunHistory actionId="action-b" />);
    await screen.findByText('route.actions.run.empty');
    expect(removeListener).toHaveBeenCalledTimes(1);
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'list', query: expect.objectContaining({ action_id: 'action-b' }) }),
      { throwError: true, showError: false }
    );

    auth.token = 'session-b';
    view.rerender(<ActionRunHistory actionId="action-b" />);
    await waitFor(() => expect(removeListener).toHaveBeenCalledTimes(2));
  });

  it.each([403, 404])('does not restore a dismissed run after a pending list response (%s)', async status => {
    const view = render(<ActionRunHistory acceptedRunIds={['run-1']} />);
    const row = await screen.findByRole('button', { name: /run-1/ });
    fireEvent.click(row);
    await screen.findByText('Invalid model response');

    const noResolve = () => {};
    let resolveList: (response: any) => void = noResolve;
    let delayNextList = false;
    dispatch.mockImplementation((request: any) => {
      if (request.kind === 'list') {
        if (delayNextList) {
          delayNextList = false;
          return new Promise(resolve => {
            resolveList = resolve;
          });
        }
        return Promise.resolve(state.list);
      }
      if (state.detail instanceof Error) {
        return Promise.reject(state.detail);
      }
      return Promise.resolve(state.detail);
    });
    delayNextList = true;
    fireEvent.click(screen.getByLabelText('route.actions.run.refresh'));
    await waitFor(() => expect(resolveList).not.toBe(noResolve));
    const listCalls = dispatch.mock.calls.filter(([request]) => request.kind === 'list').length;

    state.detail = apiError(status);
    fireEvent.click(row);
    fireEvent.click(row);
    await waitFor(() => expect(screen.queryByRole('button', { name: /run-1/ })).not.toBeInTheDocument());
    expect(dispatch.mock.calls.filter(([request]) => request.kind === 'list')).toHaveLength(listCalls);

    await act(async () => {
      resolveList({ ...state.list, items: [summary('run-1')] });
      await Promise.resolve();
    });
    expect(screen.queryByRole('button', { name: /run-1/ })).not.toBeInTheDocument();
    expect(screen.queryByText('route.actions.run.id:run-1')).not.toBeInTheDocument();
    view.unmount();
  });

  it('clears all rows without refetching when a detail 401 occurs', async () => {
    state.list = { ...state.list, items: [summary(), summary('run-other')] };
    render(<ActionRunHistory acceptedRunIds={['run-accepted']} />);
    fireEvent.click(await screen.findByRole('button', { name: /run-1/ }));
    await screen.findByText('Invalid model response');
    const listCalls = dispatch.mock.calls.filter(([request]) => request.kind === 'list').length;
    state.detail = apiError(401);
    fireEvent.click(screen.getByRole('button', { name: /run-1/ }));
    fireEvent.click(screen.getByRole('button', { name: /run-1/ }));
    await screen.findByText('route.actions.run.empty');
    expect(dispatch.mock.calls.filter(([request]) => request.kind === 'list')).toHaveLength(listCalls);
    expect(screen.queryByText('Invalid model response')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /run-other/ })).not.toBeInTheDocument();
    expect(screen.queryByText('route.actions.run.accepted.pending')).not.toBeInTheDocument();
  });

  it.each([401, 403, 404, undefined])('clears history for list response %s', async status => {
    dispatch.mockImplementation(async () => {
      if (status === undefined) {
        return undefined;
      }
      throw apiError(status);
    });
    render(<ActionRunHistory />);
    await screen.findByText('route.actions.run.empty');
    expect(screen.queryByRole('button', { name: /run-1/ })).not.toBeInTheDocument();
  });

  it('clears history when a later page is unavailable', async () => {
    state.list.has_more = true;
    dispatch.mockImplementation(async (request: any) => {
      if (request.kind === 'list' && request.query.offset) {
        throw apiError(404);
      }
      return request.kind === 'list' ? state.list : state.detail;
    });
    render(<ActionRunHistory />);
    await screen.findByRole('button', { name: /run-1/ });
    fireEvent.click(screen.getByRole('button', { name: 'route.actions.run.loadMore' }));
    await screen.findByText('route.actions.run.empty');
    expect(screen.queryByRole('button', { name: /run-1/ })).not.toBeInTheDocument();
  });
});
