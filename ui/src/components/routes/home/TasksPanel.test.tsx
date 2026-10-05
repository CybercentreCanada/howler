import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type * as TuiCore from '@tui/core';
import i18n from 'i18n';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TasksPanel from './TasksPanel';

const mockTaskSearch = vi.hoisted(() => vi.fn());
const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('@tui/core', async () => {
  const actual = await vi.importActual<typeof TuiCore>('@tui/core');
  return {
    ...actual,
    useAppUser: () => ({ user: { username: 'alice' } })
  };
});

vi.mock('api', () => ({
  default: {
    v2: {
      task: {
        search: (...args: unknown[]) => mockTaskSearch(...args)
      }
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/routes/cases/detail/CaseTask', () => ({
  default: ({ task }: { task: { summary?: string } }) => <div>{task.summary}</div>
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return {
    ...actual,
    Link: ({ children, to, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    )
  };
});

const Wrapper = ({ children }: PropsWithChildren) => <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;

const taskItem = (summary: string, caseId = 'case-1') => ({
  task: { id: `task-${summary}`, assignment: 'alice', summary, complete: false },
  case: {
    __index: 'case' as const,
    case_id: caseId,
    title: `Case ${caseId}`,
    status: 'open',
    updated: '2024-01-01T00:00:00Z'
  }
});

const page = (items: ReturnType<typeof taskItem>[], offset = 0, hasMore = false) => ({
  items,
  offset,
  rows: 25,
  has_more: hasMore
});

describe('TasksPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTaskSearch.mockReturnValue('task-request');
    mockDispatchApi.mockResolvedValue(page([taskItem('Open task')], 0, true));
  });

  it('loads one page of 25 incomplete tasks by default', async () => {
    render(<TasksPanel />, { wrapper: Wrapper });

    expect(await screen.findByText('Open task')).toBeInTheDocument();
    expect(mockTaskSearch).toHaveBeenCalledTimes(1);
    expect(mockTaskSearch).toHaveBeenCalledWith({ offset: 0, rows: 25, filter: 'incomplete' }, expect.any(AbortSignal));
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  });

  it('requests one page at a time and paginates according to has_more', async () => {
    mockDispatchApi
      .mockResolvedValueOnce(page([taskItem('First page')], 0, true))
      .mockResolvedValueOnce(page([taskItem('Second page')], 25, false))
      .mockResolvedValueOnce(page([taskItem('First page again')], 0, false));

    render(<TasksPanel />, { wrapper: Wrapper });
    expect(await screen.findByText('First page')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Second page')).toBeInTheDocument();
    expect(mockTaskSearch.mock.calls.map(([request]) => request.offset)).toEqual([0, 25]);
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(await screen.findByText('First page again')).toBeInTheDocument();
    expect(mockTaskSearch.mock.calls.map(([request]) => request.offset)).toEqual([0, 25, 0]);
  });

  it('maps each status filter to the API and resets pagination on filter changes', async () => {
    const user = userEvent.setup();
    render(<TasksPanel />, { wrapper: Wrapper });
    expect(await screen.findByText('Open task')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(mockTaskSearch).toHaveBeenCalledTimes(2));
    expect(mockTaskSearch.mock.calls[1][0]).toMatchObject({ offset: 25, filter: 'incomplete' });

    const filterSelect = screen.getByRole('combobox');
    await user.click(filterSelect);
    await user.click(screen.getByRole('option', { name: 'Completed' }));
    await waitFor(() => expect(mockTaskSearch).toHaveBeenCalledTimes(3));
    expect(mockTaskSearch.mock.calls[2][0]).toMatchObject({ offset: 0, rows: 25, filter: 'complete' });

    await user.click(filterSelect);
    await user.click(screen.getByRole('option', { name: 'All tasks' }));
    await waitFor(() => expect(mockTaskSearch).toHaveBeenCalledTimes(4));
    expect(mockTaskSearch.mock.calls[3][0]).toMatchObject({ offset: 0, filter: 'all' });

    await user.click(filterSelect);
    await user.click(screen.getByRole('option', { name: 'Not completed' }));
    await waitFor(() => expect(mockTaskSearch).toHaveBeenCalledTimes(5));
    expect(mockTaskSearch.mock.calls[4][0]).toMatchObject({ offset: 0, filter: 'incomplete' });
  });

  it('keeps the latest results and reports only the current refresh after requests overlap', async () => {
    let resolveFirst: ((value: ReturnType<typeof page>) => void) | undefined;
    let resolveSecond: ((value: ReturnType<typeof page>) => void) | undefined;
    mockDispatchApi
      .mockReturnValueOnce(new Promise(resolve => (resolveFirst = resolve)))
      .mockReturnValueOnce(new Promise(resolve => (resolveSecond = resolve)));
    const firstTick = Symbol('first');
    const secondTick = Symbol('second');
    const onRefreshComplete = vi.fn();

    const { rerender } = render(<TasksPanel refreshTick={firstTick} onRefreshComplete={onRefreshComplete} />, {
      wrapper: Wrapper
    });
    const firstSignal = mockTaskSearch.mock.calls[0][1] as AbortSignal;

    rerender(<TasksPanel refreshTick={secondTick} onRefreshComplete={onRefreshComplete} />);
    expect(firstSignal.aborted).toBe(true);

    resolveSecond?.(page([taskItem('Latest task')], 0, false));
    expect(await screen.findByText('Latest task')).toBeInTheDocument();
    await waitFor(() => expect(onRefreshComplete).toHaveBeenCalledTimes(1));
    expect(onRefreshComplete).toHaveBeenCalledWith('tasks-panel', secondTick);

    resolveFirst?.(page([taskItem('Stale task')], 0, false));
    await waitFor(() => expect(screen.queryByText('Stale task')).not.toBeInTheDocument());
    expect(screen.getByText('Latest task')).toBeInTheDocument();
    expect(onRefreshComplete).toHaveBeenCalledTimes(1);
  });

  it('backs up to the last non-empty page when a refresh finds that data has shrunk', async () => {
    mockDispatchApi
      .mockResolvedValueOnce(
        page(
          Array.from({ length: 25 }, (_, i) => taskItem(`Task ${i}`)),
          0,
          true
        )
      )
      .mockResolvedValueOnce(
        page(
          Array.from({ length: 25 }, (_, i) => taskItem(`Task ${i + 25}`)),
          25,
          true
        )
      )
      .mockResolvedValueOnce(page([taskItem('Last page task')], 50, false))
      .mockResolvedValueOnce(page([], 50, false))
      .mockResolvedValueOnce(page([taskItem('Remaining task')], 25, false));
    const refreshTick = Symbol('refresh');
    const onRefreshComplete = vi.fn();
    const { rerender } = render(<TasksPanel onRefreshComplete={onRefreshComplete} />, { wrapper: Wrapper });

    await screen.findByText('Task 0');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByText('Task 25');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Last page task')).toBeInTheDocument();

    rerender(<TasksPanel refreshTick={refreshTick} onRefreshComplete={onRefreshComplete} />);
    expect(await screen.findByText('Remaining task')).toBeInTheDocument();

    await waitFor(() => expect(mockTaskSearch).toHaveBeenCalledTimes(5));
    expect(mockTaskSearch.mock.calls.map(([request]) => request.offset)).toEqual([0, 25, 50, 50, 25]);
    await waitFor(() => expect(onRefreshComplete).toHaveBeenCalledTimes(1));
    expect(onRefreshComplete).toHaveBeenCalledWith('tasks-panel', refreshTick);
  });

  it('shows an error for failed requests and an empty state when there are no tasks', async () => {
    mockDispatchApi.mockRejectedValueOnce(new Error('request failed'));
    const { unmount } = render(<TasksPanel />, { wrapper: Wrapper });

    expect(await screen.findByText('Unable to load tasks.')).toBeInTheDocument();

    unmount();
    mockDispatchApi.mockReset().mockResolvedValue(page([]));
    render(<TasksPanel taskFilter="complete" />, { wrapper: Wrapper });
    expect(await screen.findByText('No Results')).toBeInTheDocument();
  });

  it('aborts the request and reports a pending refresh when unmounted', () => {
    const refreshTick = Symbol('refresh');
    const onRefreshComplete = vi.fn();
    mockDispatchApi.mockReturnValue(new Promise(() => {}));

    const { unmount } = render(
      <TasksPanel panelId="tasks-panel-1" refreshTick={refreshTick} onRefreshComplete={onRefreshComplete} />,
      { wrapper: Wrapper }
    );
    const signal = mockTaskSearch.mock.calls[0][1] as AbortSignal;

    unmount();

    expect(onRefreshComplete).toHaveBeenCalledTimes(1);
    expect(onRefreshComplete).toHaveBeenCalledWith('tasks-panel-1', refreshTick);
    expect(signal.aborted).toBe(true);
  });
});
