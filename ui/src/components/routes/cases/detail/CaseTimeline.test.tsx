/* eslint-disable react/no-children-prop */
/// <reference types="vitest" />
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { createElement, type FC, type PropsWithChildren } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { createMockHit, createMockObservable } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildFilters } from './CaseTimeline';

// ---------------------------------------------------------------------------
// Pure logic tests
// ---------------------------------------------------------------------------

describe('buildFilters', () => {
  it('returns an empty array when both lists are empty', () => {
    expect(buildFilters([], [])).toEqual([]);
  });

  it('builds a tactic filter', () => {
    const result = buildFilters([{ id: 'TA0001', name: 'Initial Access', kind: 'tactic' }], []);
    expect(result).toEqual(['threat.tactic.id:(TA0001)']);
  });

  it('builds a technique filter', () => {
    const result = buildFilters([{ id: 'T1059', name: 'Command Scripting', kind: 'technique' }], []);
    expect(result).toEqual(['threat.technique.id:(T1059)']);
  });

  it('OR-combines multiple tactics in one clause', () => {
    const result = buildFilters(
      [
        { id: 'TA0001', name: 'Initial Access', kind: 'tactic' },
        { id: 'TA0002', name: 'Execution', kind: 'tactic' }
      ],
      []
    );
    expect(result).toEqual(['threat.tactic.id:(TA0001 OR TA0002)']);
  });

  it('emits separate clauses for tactics and techniques', () => {
    const result = buildFilters(
      [
        { id: 'TA0001', name: 'Initial Access', kind: 'tactic' },
        { id: 'T1059', name: 'Command Scripting', kind: 'technique' }
      ],
      []
    );
    expect(result).toContain('threat.tactic.id:(TA0001)');
    expect(result).toContain('threat.technique.id:(T1059)');
    expect(result).toHaveLength(2);
  });

  it('builds an escalation filter', () => {
    const result = buildFilters([], ['evidence', 'hit']);
    expect(result).toEqual(['howler.escalation:(evidence OR hit)']);
  });

  it('combines mitre and escalation filters', () => {
    const result = buildFilters([{ id: 'TA0001', name: 'Initial Access', kind: 'tactic' }], ['evidence']);
    expect(result).toHaveLength(2);
    expect(result).toContain('threat.tactic.id:(TA0001)');
    expect(result).toContain('howler.escalation:(evidence)');
  });
});

// ---------------------------------------------------------------------------
// Component rendering tests
// ---------------------------------------------------------------------------

const mockDispatchApi = vi.fn();

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('../hooks/useCase', () => ({
  default: ({ case: c }: any) => ({ case: c, update: vi.fn(), loading: false, missing: false })
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useOutletContext: () => undefined };
});

// Stub card components — their internals are irrelevant to timeline tests
vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id }: { id: string }) => <div>{`HitCard:${id}`}</div>
}));

vi.mock('components/elements/observable/ObservableCard', () => ({
  default: ({ id }: { id: string }) => <div>{`ObservableCard:${id}`}</div>
}));

// Return the request object rather than a Promise so dispatchApi's first
// argument is JSON-serialisable (JSON.stringify(Promise) === '{}').
vi.mock('api', () => ({
  default: {
    v2: {
      search: {
        post: (_indexes: any, request: any) => request ?? {},
        facet: {
          post: (_indexes: any, request: any) => request ?? {}
        }
      }
    }
  }
}));

const mockLoadRecords = vi.fn();

const mockConfig = {
  lookups: {
    tactics: { TA0001: { key: 'TA0001', name: 'Initial Access', url: '' } },
    techniques: { T1059: { key: 'T1059', name: 'Command Scripting', url: '' } }
  }
} as any;

const mockCase = {
  case_id: 'case-001',
  items: [
    { type: 'hit', value: 'hit-1', path: 'hits/hit-1' },
    { type: 'observable', value: 'obs-1', path: 'observables/obs-1' }
  ]
} as any;

const Wrapper: FC<PropsWithChildren> = ({ children }) => (
  <ApiConfigContext.Provider value={{ config: mockConfig, setConfig: vi.fn() }}>
    <RecordContext.Provider value={{ records: {}, loadRecords: mockLoadRecords } as any}>
      <MemoryRouter initialEntries={['/cases/case-001/timeline']}>{children}</MemoryRouter>
    </RecordContext.Provider>
  </ApiConfigContext.Provider>
);

const mockConfigWithUrls = {
  lookups: {
    tactics: { TA0001: { key: 'TA0001', name: 'Initial Access', url: 'https://attack.mitre.org/tactics/TA0001' } },
    techniques: {
      T1059: { key: 'T1059', name: 'Command Scripting', url: 'https://attack.mitre.org/techniques/T1059' }
    }
  }
} as any;

const WrapperWithUrl: FC<PropsWithChildren> = ({ children }) => (
  <ApiConfigContext.Provider value={{ config: mockConfigWithUrls, setConfig: vi.fn() }}>
    <RecordContext.Provider value={{ records: {}, loadRecords: mockLoadRecords } as any}>
      <MemoryRouter initialEntries={['/cases/case-001/timeline']}>{children}</MemoryRouter>
    </RecordContext.Provider>
  </ApiConfigContext.Provider>
);

const CaseTimeline = (await import('./CaseTimeline')).default;

// Reusable mock response factories
const mockFacetResponse = {
  'threat.tactic.id': { TA0001: 1 },
  'threat.technique.id': { T1059: 1 },
  'howler.escalation': { evidence: 2, hit: 1 }
};

const mockSearchResponse = (
  items = [
    createMockHit({ howler: { id: 'hit-1' }, event: { created: '2024-01-01T00:00:00Z' } }),
    createMockObservable({ howler: { id: 'obs-1' } })
  ]
) => ({ items, total: items.length, rows: items.length, offset: 0 });

describe('CaseTimeline component', () => {
  beforeEach(() => {
    mockDispatchApi.mockClear();
    mockLoadRecords.mockClear();
  });

  it('renders loading skeletons while the search is pending', () => {
    mockDispatchApi.mockReturnValue(new Promise(() => {})); // never resolves

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    expect(document.querySelectorAll('.MuiSkeleton-root').length).toBeGreaterThan(0);
  });

  it('shows the empty state when no entries are returned', async () => {
    mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(mockSearchResponse([]));

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('page.cases.timeline.empty');
  });

  it('renders HitCard for hit entries and ObservableCard for observable entries', async () => {
    mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(mockSearchResponse());

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    expect(await screen.findByText('HitCard:hit-1')).toBeTruthy();
    expect(screen.getByText('ObservableCard:obs-1')).toBeTruthy();
  });

  it('renders the formatted event.created timestamp for hits', async () => {
    mockDispatchApi
      .mockResolvedValueOnce(mockFacetResponse)
      .mockResolvedValueOnce(
        mockSearchResponse([createMockHit({ howler: { id: 'hit-1' }, event: { created: '2024-06-15T12:34:56Z' } })])
      );

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText(/2024-06-15/);
  });

  it('falls back to entry.timestamp when event.created is absent', async () => {
    const entry = createMockHit({ howler: { id: 'hit-1' } });
    (entry as any).timestamp = '2024-03-10T08:00:00Z';
    delete (entry as any).event;

    mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(mockSearchResponse([entry]));

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText(/2024-03-10/);
  });

  it('calls loadRecords with the search results', async () => {
    const items = [createMockHit({ howler: { id: 'hit-1' } })];
    mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(mockSearchResponse(items));

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('HitCard:hit-1');

    expect(mockLoadRecords).toHaveBeenCalledWith(items);
  });

  it('renders MITRE autocomplete with options derived from the facet response', async () => {
    mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(mockSearchResponse());

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('HitCard:hit-1');

    expect(screen.getByRole('combobox', { name: /page.cases.timeline.filter.mitre/i })).toBeTruthy();
  });

  it('renders escalation autocomplete pre-populated with "evidence"', async () => {
    mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(mockSearchResponse());

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

    await screen.findByText('HitCard:hit-1');

    // "evidence" chip should be pre-selected as a tag
    expect(screen.getByText('evidence')).toBeTruthy();
  });

  it('re-fetches with an escalation filter when a new escalation is selected', async () => {
    mockDispatchApi
      .mockResolvedValueOnce(mockFacetResponse)
      .mockResolvedValueOnce(mockSearchResponse())
      .mockResolvedValueOnce(mockSearchResponse());

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('HitCard:hit-1');

    const escalationInput = screen.getByRole('combobox', { name: /page.cases.timeline.filter.escalation/i });
    await act(async () => {
      await userEvent.click(escalationInput);
    });

    const option = await screen.findByRole('option', { name: /\bhit\b/i });
    await act(async () => {
      await userEvent.click(option);
    });

    // The third dispatchApi call should carry a filter containing "hit"
    const thirdCallArgs = mockDispatchApi.mock.calls[2];
    expect(JSON.stringify(thirdCallArgs[0])).toContain('hit');
  });

  it('re-fetches when a MITRE tactic is selected', async () => {
    mockDispatchApi
      .mockResolvedValueOnce(mockFacetResponse)
      .mockResolvedValueOnce(mockSearchResponse())
      .mockResolvedValueOnce(mockSearchResponse());

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('HitCard:hit-1');

    const mitreInput = screen.getByRole('combobox', { name: /page.cases.timeline.filter.mitre/i });
    await act(async () => {
      await userEvent.click(mitreInput);
    });

    const tacticOption = await screen.findByRole('option', { name: /TA0001/i });
    await act(async () => {
      await userEvent.click(tacticOption);
    });

    const thirdCallArgs = mockDispatchApi.mock.calls[2];
    expect(JSON.stringify(thirdCallArgs[0])).toContain('TA0001');
  });

  it('passes the case item ids in the base query on every search call', async () => {
    mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(mockSearchResponse());

    render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });
    await screen.findByText('HitCard:hit-1');

    const searchCallArg = mockDispatchApi.mock.calls[1][0];
    expect(JSON.stringify(searchCallArg)).toContain('hit-1');
    expect(JSON.stringify(searchCallArg)).toContain('obs-1');
  });

  it('renders nothing when _case is not yet available', () => {
    const emptyCaseWrapper: FC<PropsWithChildren> = ({ children }) =>
      createElement(
        ApiConfigContext.Provider,
        { value: { config: mockConfig, setConfig: vi.fn() }, children: null },
        createElement(
          RecordContext.Provider,
          { value: { records: {}, loadRecords: mockLoadRecords } as any, children: null },
          createElement(MemoryRouter, null, children)
        )
      );

    const { container } = render(<CaseTimeline />, { wrapper: emptyCaseWrapper });
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing and skips fetching when the case has no items', () => {
    mockDispatchApi.mockResolvedValue({});

    render(<CaseTimeline case={{ case_id: 'empty', items: [] } as any} />, { wrapper: Wrapper });

    expect(mockDispatchApi).not.toHaveBeenCalled();
  });

  describe('tactic and technique inline entries', () => {
    it('renders the technique ID link for a hit with threat.technique', async () => {
      mockDispatchApi
        .mockResolvedValueOnce(mockFacetResponse)
        .mockResolvedValueOnce(
          mockSearchResponse([createMockHit({ howler: { id: 'hit-1' }, threat: { technique: { id: 'T1059' } } })])
        );

      render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

      expect(await screen.findByText('T1059')).toBeTruthy();
    });

    it('renders the tactic ID link for a hit with threat.tactic', async () => {
      mockDispatchApi
        .mockResolvedValueOnce(mockFacetResponse)
        .mockResolvedValueOnce(
          mockSearchResponse([createMockHit({ howler: { id: 'hit-1' }, threat: { tactic: { id: 'TA0001' } } })])
        );

      render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

      expect(await screen.findByText('TA0001')).toBeTruthy();
    });

    it('renders both technique and tactic ID links when the entry has both threat fields', async () => {
      mockDispatchApi.mockResolvedValueOnce(mockFacetResponse).mockResolvedValueOnce(
        mockSearchResponse([
          createMockHit({
            howler: { id: 'hit-1' },
            threat: { technique: { id: 'T1059' }, tactic: { id: 'TA0001' } }
          })
        ])
      );

      render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

      await screen.findByText('T1059');
      expect(screen.getByText('TA0001')).toBeTruthy();
    });

    it('does not render tactic or technique links when threat data is absent', async () => {
      mockDispatchApi
        .mockResolvedValueOnce(mockFacetResponse)
        .mockResolvedValueOnce(mockSearchResponse([createMockHit({ howler: { id: 'hit-1' } })]));

      render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

      await screen.findByText('HitCard:hit-1');
      expect(screen.queryByText('T1059')).toBeNull();
      expect(screen.queryByText('TA0001')).toBeNull();
    });

    it('sets href on the technique link from config.lookups.techniques.url', async () => {
      mockDispatchApi
        .mockResolvedValueOnce(mockFacetResponse)
        .mockResolvedValueOnce(
          mockSearchResponse([createMockHit({ howler: { id: 'hit-1' }, threat: { technique: { id: 'T1059' } } })])
        );

      render(<CaseTimeline case={mockCase} />, { wrapper: WrapperWithUrl });

      const link = await screen.findByText('T1059');
      expect(link.getAttribute('href')).toBe('https://attack.mitre.org/techniques/T1059');
    });

    it('sets href on the tactic link from config.lookups.tactics.url', async () => {
      mockDispatchApi
        .mockResolvedValueOnce(mockFacetResponse)
        .mockResolvedValueOnce(
          mockSearchResponse([createMockHit({ howler: { id: 'hit-1' }, threat: { tactic: { id: 'TA0001' } } })])
        );

      render(<CaseTimeline case={mockCase} />, { wrapper: WrapperWithUrl });

      const link = await screen.findByText('TA0001');
      expect(link.getAttribute('href')).toBe('https://attack.mitre.org/tactics/TA0001');
    });

    describe('tooltip content', () => {
      beforeEach(() => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
      });

      afterEach(() => {
        vi.useRealTimers();
      });

      it('shows a tooltip with technique ID and name on hover', async () => {
        mockDispatchApi
          .mockResolvedValueOnce(mockFacetResponse)
          .mockResolvedValueOnce(
            mockSearchResponse([createMockHit({ howler: { id: 'hit-1' }, threat: { technique: { id: 'T1059' } } })])
          );

        render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

        const link = await screen.findByText('T1059');

        await act(async () => {
          await userEvent.hover(link);
        });

        const tooltip = await screen.findByRole('tooltip');
        expect(tooltip.textContent).toContain('T1059: Command Scripting');
      });

      it('shows a tooltip with tactic ID and name on hover', async () => {
        mockDispatchApi
          .mockResolvedValueOnce(mockFacetResponse)
          .mockResolvedValueOnce(
            mockSearchResponse([createMockHit({ howler: { id: 'hit-1' }, threat: { tactic: { id: 'TA0001' } } })])
          );

        render(<CaseTimeline case={mockCase} />, { wrapper: Wrapper });

        const link = await screen.findByText('TA0001');

        await act(async () => {
          await userEvent.hover(link);
        });

        const tooltip = await screen.findByRole('tooltip');
        expect(tooltip.textContent).toContain('TA0001: Initial Access');
      });
    });
  });
});
