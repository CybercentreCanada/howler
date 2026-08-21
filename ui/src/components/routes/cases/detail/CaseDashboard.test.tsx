import { render, waitFor } from '@testing-library/react';
import { RecordContext, type RecordContextType } from 'components/app/providers/RecordProvider';
import type { Case } from 'models/entities/generated/Case';
import { useState, type FC, type PropsWithChildren } from 'react';
import { createMockCase, createMockEvent, createMockHit } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSearchPost = vi.hoisted(() => vi.fn());
const mockUpdateCase = vi.hoisted(() => vi.fn());
const mockUseCaseState = vi.hoisted(() => ({ case: null as Case | null }));
const mockAggregateProps = vi.hoisted(() => ({
  current: [] as Array<Record<string, unknown>>
}));
const mockCaseOverviewProps = vi.hoisted(() => ({ current: [] as Array<Record<string, unknown>> }));
const mockTaskPanelProps = vi.hoisted(() => ({ current: [] as Array<Record<string, unknown>> }));
const mockAlertPanelProps = vi.hoisted(() => ({ current: [] as Array<Record<string, unknown>> }));
const mockRelatedCasePanelProps = vi.hoisted(() => ({ current: [] as Array<Record<string, unknown>> }));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('use-context-selector', async () => {
  const react = (await vi.importActual('react')) as { createContext: any; useContext: any };

  return {
    createContext: react.createContext,
    useContextSelector: (context: any, selector: (value: any) => any) => {
      return (selector as any)(react.useContext(context));
    }
  };
});

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    v2: {
      search: {
        post: (...args: unknown[]) => mockSearchPost(...args)
      }
    }
  }
}));

vi.mock('../hooks/useCase', () => ({
  default: () => ({
    case: mockUseCaseState.case,
    update: mockUpdateCase
  })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useOutletContext: () => createMockCase({ case_id: 'route-case-id', items: [] })
  };
});

vi.mock('./aggregates/CaseAggregate', () => ({
  default: (props: Record<string, unknown>) => {
    mockAggregateProps.current.push(props);
    return <div id={`aggregate-${String(mockAggregateProps.current.length)}`} />;
  }
}));

vi.mock('./CaseOverview', () => ({
  default: (props: Record<string, unknown>) => {
    mockCaseOverviewProps.current.push(props);
    return <div id="case-overview" />;
  }
}));

vi.mock('./TaskPanel', () => ({
  default: (props: Record<string, unknown>) => {
    mockTaskPanelProps.current.push(props);
    return <div id="task-panel" />;
  }
}));

vi.mock('./AlertPanel', () => ({
  default: (props: Record<string, unknown>) => {
    mockAlertPanelProps.current.push(props);
    return <div id="alert-panel" />;
  }
}));

vi.mock('./RelatedCasePanel', () => ({
  default: (props: Record<string, unknown>) => {
    mockRelatedCasePanelProps.current.push(props);
    return <div id="related-case-panel" />;
  }
}));

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import CaseDashboard from './CaseDashboard';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeRecordContextValue = (
  records: Record<string, any>,
  loadRecords: RecordContextType['loadRecords']
): RecordContextType => ({
  records,
  selectedRecords: [],
  addRecordToSelection: vi.fn(),
  removeRecordFromSelection: vi.fn(),
  clearSelectedRecords: vi.fn(),
  loadRecords,
  updateRecord: vi.fn(),
  getRecord: vi.fn()
});

const renderDashboard = ({
  dashboardCase,
  initialRecords = {},
  onLoadRecords
}: {
  dashboardCase: Case;
  initialRecords?: Record<string, any>;
  onLoadRecords?: (items: any[]) => void;
}) => {
  const Wrapper: FC<PropsWithChildren> = ({ children }) => {
    const [records, setRecords] = useState<Record<string, any>>(initialRecords);

    const loadRecords: RecordContextType['loadRecords'] = items => {
      onLoadRecords?.(items);

      const mapped = Object.fromEntries(items.map(item => [item.howler.id, item]));
      setRecords(prev => ({ ...prev, ...mapped }));
    };

    return (
      <RecordContext.Provider value={makeRecordContextValue(records, loadRecords)}>{children}</RecordContext.Provider>
    );
  };

  return render(<CaseDashboard case={dashboardCase} />, { wrapper: Wrapper });
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockSearchPost.mockReset();
  mockUpdateCase.mockReset();

  mockAggregateProps.current = [];
  mockCaseOverviewProps.current = [];
  mockTaskPanelProps.current = [];
  mockAlertPanelProps.current = [];
  mockRelatedCasePanelProps.current = [];

  mockUseCaseState.case = null;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseDashboard', () => {
  it('renders nothing when useCase does not return a case', () => {
    const baseCase = createMockCase({ case_id: 'case-1', items: [] });
    mockUseCaseState.case = null;

    const { container } = renderDashboard({ dashboardCase: baseCase });

    expect(container).toBeEmptyDOMElement();
  });

  it('renders overview, panels and aggregate cards with translated subtitles', () => {
    const dashboardCase = createMockCase({
      case_id: 'case-2',
      items: [
        { type: 'hit', value: 'hit-1' },
        { type: 'event', value: 'event-1' }
      ]
    });

    mockUseCaseState.case = dashboardCase;

    renderDashboard({
      dashboardCase,
      initialRecords: {
        'hit-1': createMockHit({ howler: { id: 'hit-1', outline: { threat: 'threat-a', target: 'target-a' } } } as any),
        'event-1': createMockEvent({ howler: { id: 'event-1', outline: { indicators: ['ioc-a'] } as any } })
      }
    });

    expect(mockCaseOverviewProps.current).toHaveLength(1);
    expect(mockTaskPanelProps.current).toHaveLength(1);
    expect(mockAlertPanelProps.current).toHaveLength(1);
    expect(mockRelatedCasePanelProps.current).toHaveLength(1);
    expect(mockAggregateProps.current).toHaveLength(4);

    expect(mockAggregateProps.current[0]).toEqual(
      expect.objectContaining({
        field: 'howler.outline.threat',
        subtitle: 'page.cases.dashboard.threat'
      })
    );
    expect(mockAggregateProps.current[1]).toEqual(
      expect.objectContaining({
        field: 'howler.outline.target',
        subtitle: 'page.cases.dashboard.target'
      })
    );
    expect(mockAggregateProps.current[2]).toEqual(
      expect.objectContaining({
        field: 'howler.outline.indicators',
        subtitle: 'page.cases.dashboard.indicators'
      })
    );
    expect(mockAggregateProps.current[3]).toEqual(
      expect.objectContaining({
        subtitle: 'page.cases.dashboard.duration',
        title: '--'
      })
    );
  });

  it('loads missing hit and event records and sends expected search query', async () => {
    const dashboardCase = createMockCase({
      case_id: 'case-3',
      items: [
        { type: 'hit', value: 'hit-1' },
        { type: 'event', value: 'event-1' },
        { type: 'hit', value: 'hit-2' },
        { type: 'case', value: 'case-child' }
      ]
    });

    mockUseCaseState.case = dashboardCase;

    const loadedEvent = createMockEvent({ howler: { id: 'event-1' } });
    const loadedHit = createMockHit({ howler: { id: 'hit-2' } });
    mockSearchPost.mockReturnValue({ endpoint: 'search' });
    mockDispatchApi.mockResolvedValue({
      items: [loadedEvent, loadedHit]
    });

    const onLoadRecords = vi.fn();

    renderDashboard({
      dashboardCase,
      initialRecords: {
        'hit-1': createMockHit({ howler: { id: 'hit-1' } })
      },
      onLoadRecords
    });

    await waitFor(() => {
      expect(mockSearchPost).toHaveBeenCalledWith(['hit', 'event'], {
        query: 'howler.id:(event-1 OR hit-2)',
        metadata: ['template', 'analytic']
      });
      expect(mockDispatchApi).toHaveBeenCalledTimes(1);
      expect(onLoadRecords).toHaveBeenCalledWith([loadedEvent, loadedHit]);
    });
  });
});
