import { render, screen, waitFor } from '@testing-library/react';
import type * as TuiCore from '@tui/core';
import i18n from 'i18n';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TasksPanel from './TasksPanel';

const mockSearchPost = vi.hoisted(() => vi.fn());
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
      search: {
        post: (...args: unknown[]) => mockSearchPost(...args)
      }
    }
  }
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/routes/cases/detail/CaseTask', () => ({
  default: ({ task }: any) => <div>{task.summary}</div>
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

describe('TasksPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchPost.mockReturnValue('task-request');
    mockDispatchApi.mockResolvedValue({
      items: [
        {
          __index: 'case',
          case_id: 'case-1',
          title: 'Case One',
          tasks: [
            { id: 'task-1', assignment: 'alice', summary: 'Open task', complete: false },
            { id: 'task-2', assignment: 'alice', summary: 'Done task', complete: true },
            { id: 'task-3', assignment: 'bob', summary: 'Other user task', complete: false }
          ]
        }
      ],
      total: 1
    });
  });

  it('defaults to showing only your incomplete tasks', async () => {
    const { queryByText } = render(<TasksPanel />, { wrapper: Wrapper });

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
    expect(mockSearchPost).toHaveBeenCalledWith('case', {
      query: 'case_id:*',
      filters: ['tasks.assignment:"alice"'],
      rows: 150,
      offset: 0,
      sort: 'created desc'
    });
    expect(await screen.findByText('Open task')).toBeInTheDocument();
    expect(queryByText('Done task')).not.toBeInTheDocument();
    expect(queryByText('Other user task')).not.toBeInTheDocument();
  });

  it('can show completed tasks', async () => {
    render(<TasksPanel taskFilter="complete" />, { wrapper: Wrapper });

    expect(await screen.findByText('Done task')).toBeInTheDocument();
    expect(screen.queryByText('Open task')).not.toBeInTheDocument();
  });
});
