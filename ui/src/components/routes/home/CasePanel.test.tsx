import { render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18n';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CasePanel from './CasePanel';

const mockSearchPost = vi.hoisted(() => vi.fn());
const mockDispatchApi = vi.hoisted(() => vi.fn());

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

vi.mock('components/routes/cases/search/CaseStatusFilter', () => ({
  default: () => <div>status-filter</div>
}));

vi.mock('components/routes/cases/search/CaseAssigneeFilter', () => ({
  default: () => <div>assignee-filter</div>
}));

vi.mock('components/routes/cases/search/CaseDateFilter', () => ({
  default: () => <div>date-filter</div>
}));

vi.mock('components/elements/case/CaseCard', () => ({
  default: ({ case: _case }: any) => <div>{_case.title}</div>
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

describe('CasePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchPost.mockReturnValue('case-request');
    mockDispatchApi.mockResolvedValue({
      items: [{ case_id: 'case-1', title: 'Case One', __index: 'case' }]
    });
  });

  it('loads cases with the configured filters', async () => {
    render(<CasePanel statusFilter={['open']} assigneeFilter={['alice']} dateRange="date.range.1.day" />, {
      wrapper: Wrapper
    });

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());

    expect(mockSearchPost).toHaveBeenCalledWith('case', {
      query: 'case_id:*',
      filters: ['status:("open")', '(participants:"alice" OR tasks.assignment:"alice")', 'created:[now-1d/d TO now]'],
      rows: 10,
      sort: 'created desc'
    });
    expect(await screen.findByText('Case One')).toBeInTheDocument();
  });

  it('renders all three case filters', async () => {
    render(<CasePanel />, { wrapper: Wrapper });

    expect(screen.getByText('status-filter')).toBeInTheDocument();
    expect(screen.getByText('assignee-filter')).toBeInTheDocument();
    expect(screen.getByText('date-filter')).toBeInTheDocument();
    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
  });
});
