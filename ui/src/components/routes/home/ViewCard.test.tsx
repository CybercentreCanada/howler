import { render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18n';
import type { PropsWithChildren } from 'react';
import React, { useCallback, useState } from 'react';
import { I18nextProvider } from 'react-i18next';
import { setupContextSelectorMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ViewCard from './ViewCard';

setupContextSelectorMock();

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockFetchViews = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockBuildViewUrl = vi.hoisted(() => vi.fn(() => '/views/view-1'));

vi.mock('api', () => ({
  default: {
    v2: {
      search: {
        post: (...args: unknown[]) => mockSearchPost(...args)
      }
    }
  }
}));

const mockSearchPost = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-router-dom', async () => {
  // oxlint-disable-next-line consistent-type-imports
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    Link: ({ children, to, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
    useNavigate: () => mockNavigate
  };
});

vi.mock('utils/viewUtils', () => ({
  buildViewUrl: mockBuildViewUrl
}));

const mockView = {
  view_id: 'view-1',
  title: 'My View',
  query: 'howler.status:open',
  indexes: ['hit'],
  sort: 'event.created desc',
  span: 'date.range.1.month',
  type: 'personal',
  owner: 'test-user',
  settings: { advance_on_triage: false }
};

vi.mock('components/app/providers/ViewProvider', () => ({
  ViewContext: React.createContext<any>(null)
}));

vi.mock('components/app/providers/RecordProvider', () => {
  const recordContext = React.createContext<any>(null);
  return {
    RecordContext: recordContext,
    useRecordContextSelector: (selector: (context: any) => unknown) => selector(React.useContext(recordContext))
  };
});

vi.mock('components/elements/hit/HitBanner', () => ({
  default: ({ hit }: any) => <div>Hit: {hit.howler.id}</div>
}));

vi.mock('components/elements/event/EventCard', () => ({
  default: ({ event }: any) => <div>Event: {event.howler.id}</div>
}));

vi.mock('components/elements/record/RecordContextMenu', () => ({
  default: ({ children }: PropsWithChildren) => <div>{children}</div>
}));

vi.mock('commons/components/display/AppListEmpty', () => ({
  default: () => <div>No records</div>
}));

import { RecordContext } from 'components/app/providers/RecordProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';

const hit = {
  __index: 'hit',
  howler: {
    id: 'hit-1',
    status: 'open',
    assignment: null,
    assessment: null
  }
};

const event = {
  __index: 'event',
  howler: { id: 'event-1' }
};

const Wrapper = ({ children }: PropsWithChildren) => {
  const [records, setRecords] = useState<Record<string, any>>({});
  const loadRecords = useCallback((newRecords: any[]) => {
    setRecords(current => ({
      ...current,
      ...Object.fromEntries(newRecords.map(record => [record.howler.id, record]))
    }));
  }, []);

  const recordContext = {
    records,
    loadRecords
  };

  return (
    <I18nextProvider i18n={i18n as any}>
      <ViewContext.Provider value={{ views: { 'view-1': mockView }, fetchViews: mockFetchViews } as any}>
        <RecordContext.Provider value={recordContext as any}>{children}</RecordContext.Provider>
      </ViewContext.Provider>
    </I18nextProvider>
  );
};

describe('ViewCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchPost.mockResolvedValue({ items: [] });
    mockDispatchApi.mockImplementation((request: unknown) => request);
  });

  it('fetches the view and searches with its query and limit', async () => {
    mockSearchPost.mockReturnValue('search-request');
    mockDispatchApi.mockResolvedValue({ items: [] });

    render(<ViewCard viewId="view-1" limit={3} />, { wrapper: Wrapper });

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());

    expect(mockFetchViews).toHaveBeenCalledWith(['view-1']);
    expect(mockSearchPost).toHaveBeenCalledWith(['hit'], {
      query: mockView.query,
      rows: 3,
      metadata: ['analytic']
    });
  });

  it('renders the empty state when the search has no records', async () => {
    mockDispatchApi.mockResolvedValue({ items: [] });

    render(<ViewCard viewId="view-1" limit={3} />, { wrapper: Wrapper });

    expect(await screen.findByText('No records')).toBeInTheDocument();
  });

  it('renders hits and events returned by the search', async () => {
    mockDispatchApi.mockResolvedValue({ items: [hit, event] });

    render(<ViewCard viewId="view-1" limit={3} />, { wrapper: Wrapper });

    expect(await screen.findByText('Hit: hit-1')).toBeInTheDocument();
    expect(screen.getByText('Event: event-1')).toBeInTheDocument();
  });

  it('renders a link to the view query', async () => {
    mockDispatchApi.mockResolvedValue({ items: [hit] });

    render(<ViewCard viewId="view-1" limit={3} />, { wrapper: Wrapper });

    await screen.findByText('Hit: hit-1');
    expect(screen.getByRole('link')).toHaveAttribute('href', '/views/view-1');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('refreshes when refreshTick changes and reports completion', async () => {
    const onRefreshComplete = vi.fn();
    mockDispatchApi.mockResolvedValue({ items: [] });
    const { rerender } = render(
      <ViewCard viewId="view-1" limit={3} refreshTick={Symbol('first')} onRefreshComplete={onRefreshComplete} />,
      { wrapper: Wrapper }
    );

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(1));
    expect(onRefreshComplete).toHaveBeenCalledTimes(2);

    rerender(
      <ViewCard viewId="view-1" limit={3} refreshTick={Symbol('second')} onRefreshComplete={onRefreshComplete} />
    );

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));
    expect(onRefreshComplete).toHaveBeenCalledTimes(3);
  });
});
