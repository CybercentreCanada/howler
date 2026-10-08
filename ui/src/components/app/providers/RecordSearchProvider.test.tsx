// @ts-nocheck
import { act, renderHook, waitFor } from '@testing-library/react';
import { hpost } from 'api';
import { cloneDeep } from 'lodash-es';
import { setupContextSelectorMock, setupLocalStorageMock } from 'tests/mocks';
import { useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY, MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';
import ParameterProvider, { ParameterContext, type ParameterContextType } from './ParameterProvider';
import { RecordContext, type RecordContextType } from './RecordProvider';
import RecordSearchProvider, { RecordSearchContext } from './RecordSearchProvider';
import { ViewContext, type ViewContextType } from './ViewProvider';

vi.mock('api', { spy: true });

setupContextSelectorMock();
const mockLocalStorage = setupLocalStorageMock();

import { useLocation, useParams, useSearchParams } from 'react-router';

const mockSetParams = vi.fn();
const mockParams = vi.mocked(useParams);
const mockLocation = vi.mocked(useLocation());
let mockSearchParams = new URLSearchParams();

const mockViewContext: Partial<ViewContextType> = {
  getCurrentViews: ({ views } = {}) =>
    Promise.resolve([{ view_id: views?.[0] || 'test_view_id', query: 'howler.id:*' }])
};
const originalMockViewContext = cloneDeep(mockViewContext);
let mockParameterContext: Partial<ParameterContextType> = {
  filters: [],
  span: 'date.range.1.week',
  sort: 'event.created desc',
  query: 'howler.analytic:*',
  disabledFilterIndexes: [],
  disabledViewIndexes: [],
  setQuery: query => (mockParameterContext.query = query),
  offset: 0,
  setOffset: offset => {
    mockParameterContext.offset = parseInt(offset as any);
  },
  views: [],
  indexes: ['hit'],
  addView: vi.fn()
};
const originalMockParameterContext = cloneDeep(mockParameterContext);

const mockHitContext: Partial<RecordContextType> = {
  records: {},
  loadRecords: hits => {
    mockHitContext.records = {
      ...mockHitContext.records,
      ...Object.fromEntries(hits.map(hit => [hit.howler.id, hit]))
    };
  }
};

const Wrapper = ({ children }) => {
  return (
    <ViewContext.Provider value={mockViewContext as any}>
      <ParameterContext.Provider value={mockParameterContext as any}>
        <RecordContext.Provider value={mockHitContext as any}>
          <RecordSearchProvider>{children}</RecordSearchProvider>
        </RecordContext.Provider>
      </ParameterContext.Provider>
    </ViewContext.Provider>
  );
};

const ParameterProviderWrapper = ({ children }) => {
  return (
    <ViewContext.Provider value={mockViewContext as any}>
      <ParameterProvider>
        <RecordContext.Provider value={mockHitContext as any}>
          <RecordSearchProvider>{children}</RecordSearchProvider>
        </RecordContext.Provider>
      </ParameterProvider>
    </ViewContext.Provider>
  );
};

beforeEach(() => {
  Object.assign(mockViewContext, originalMockViewContext, { defaultView: undefined });
  mockParameterContext = cloneDeep(originalMockParameterContext);
  vi.mocked(originalMockParameterContext.addView).mockClear();

  mockLocalStorage.clear();

  mockSetParams.mockReset();

  mockLocation.pathname = '/hits';
  mockLocation.search = '';

  mockParams.mockReturnValue({ id: undefined });

  vi.mocked(hpost).mockClear();

  mockSearchParams = new URLSearchParams();
  vi.mocked(useSearchParams).mockReturnValue([mockSearchParams, mockSetParams]);
});

const expectSearchRequest = request => {
  const requests = vi
    .mocked(hpost)
    .mock.calls.filter(([url]) => url === '/api/v2/search/hit')
    .map(([, body]) => body);

  expect(requests).toEqual(expect.arrayContaining([expect.objectContaining(request)]));
};

const makeMockSetParamsUpdateUrl = () => {
  mockSetParams.mockImplementation(nextParams => {
    const replacement = typeof nextParams === 'function' ? nextParams(mockSearchParams) : nextParams;
    const updatedParams = new URLSearchParams(replacement);
    for (const key of [...mockSearchParams.keys()]) {
      mockSearchParams.delete(key);
    }
    updatedParams.forEach((value, key) => mockSearchParams.append(key, value));
    mockLocation.search = `?${mockSearchParams.toString()}`;
  });
};

describe('RecordSearchContext', () => {
  it('should initialize with default values', async () => {
    const hook = renderHook(
      () =>
        useContextSelector(RecordSearchContext, ctx => ({
          displayType: ctx.displayType,
          searching: ctx.searching,
          error: ctx.error,
          response: ctx.response,
          fzfSearch: ctx.fzfSearch
        })),
      { wrapper: Wrapper }
    );

    expect(hook.result.current.displayType).toBe('list');
    expect(hook.result.current.searching).toBe(false);
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.response).toBeNull();
    expect(hook.result.current.fzfSearch).toBe(false);
  });

  it('should initialize queryHistory from localStorage', () => {
    const mockHistory = { 'test:query': new Date().toISOString() };
    mockLocalStorage.setItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.QUERY_HISTORY}`, JSON.stringify(mockHistory));

    const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.queryHistory), {
      wrapper: Wrapper
    });

    expect(hook.result.current).toEqual(mockHistory);
  });

  describe('setDisplayType', () => {
    it('should update display type', () => {
      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            displayType: ctx.displayType,
            setDisplayType: ctx.setDisplayType
          })),
        { wrapper: Wrapper }
      );

      expect(hook.result.current.displayType).toBe('list');

      act(() => {
        hook.result.current.setDisplayType('grid');
      });

      expect(hook.result.current.displayType).toBe('grid');
    });
  });

  describe('setFzfSearch', () => {
    it('should update fzfSearch state', () => {
      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            fzfSearch: ctx.fzfSearch,
            setFzfSearch: ctx.setFzfSearch
          })),
        { wrapper: Wrapper }
      );

      expect(hook.result.current.fzfSearch).toBe(false);

      act(() => {
        hook.result.current.setFzfSearch(true);
      });

      expect(hook.result.current.fzfSearch).toBe(true);
    });
  });

  describe('setQueryHistory', () => {
    it('should update query history', () => {
      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            queryHistory: ctx.queryHistory,
            setQueryHistory: ctx.setQueryHistory
          })),
        { wrapper: Wrapper }
      );

      const newHistory = { 'new:query': new Date().toISOString() };

      act(() => {
        hook.result.current.setQueryHistory(newHistory);
      });

      expect(hook.result.current.queryHistory).toEqual(newHistory);
    });
  });

  describe('search', () => {
    it('should retain negated wildcard filters and omit positive placeholders', async () => {
      mockParameterContext.filters = ['howler.assessment:*', '-howler.assessment:*'];

      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.getFilters), {
        wrapper: Wrapper
      });

      const filters = await hook.result.current();

      expect(filters).toContain('-howler.assessment:*');
      expect(filters).not.toContain('howler.assessment:*');
    });

    it('should omit disabled filters from the effective search request without changing enabled negative filters', async () => {
      mockParameterContext.filters = ['howler.status:open', '-howler.assessment:*'];
      mockParameterContext.disabledFilterIndexes = [0];

      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

      act(() => {
        hook.result.current('test query');
      });

      await waitFor(() => {
        expectSearchRequest({
          query: 'test query',
          filters: expect.arrayContaining(['-howler.assessment:*'])
        });
        expectSearchRequest({ filters: expect.not.arrayContaining(['howler.status:open']) });
      });
    });

    it('applies copied-link disabled markers to the effective search on load', async () => {
      const filters = [
        'event.provider:"azure"',
        '-howler.outline.indicators:("a" OR "b")',
        'opaque clause [x TO y]',
        'howler.status:open'
      ];
      filters.forEach(filter => mockSearchParams.append('filter', filter));
      filters.slice(0, 3).forEach(filter => mockSearchParams.append('disabled_filter', filter));
      mockLocation.search = `?${mockSearchParams.toString()}`;

      const hook = renderHook(
        () => ({
          filters: useContextSelector(ParameterContext, ctx => ctx.filters),
          disabledFilterIndexes: useContextSelector(ParameterContext, ctx => ctx.disabledFilterIndexes),
          getFilters: useContextSelector(RecordSearchContext, ctx => ctx.getFilters),
          search: useContextSelector(RecordSearchContext, ctx => ctx.search)
        }),
        { wrapper: ParameterProviderWrapper }
      );

      expect(hook.result.current.filters).toEqual(filters);
      expect(hook.result.current.disabledFilterIndexes).toEqual([0, 1, 2]);
      const effectiveFilters = await hook.result.current.getFilters();
      expect(effectiveFilters).toContain('howler.status:open');
      filters.slice(0, 3).forEach(filter => expect(effectiveFilters).not.toContain(filter));

      await waitFor(() => {
        expectSearchRequest({
          query: DEFAULT_QUERY,
          filters: expect.arrayContaining(['howler.status:open'])
        });
        expectSearchRequest({
          filters: expect.not.arrayContaining(filters.slice(0, 3))
        });
      });
    });

    it('runs the default search when a copied link loads with only disabled effective filters', async () => {
      const filter = 'howler.status:open';
      mockSearchParams.append('filter', filter);
      mockSearchParams.append('disabled_filter', filter);
      mockLocation.search = `?${mockSearchParams.toString()}`;

      const hook = renderHook(
        () => ({
          filters: useContextSelector(ParameterContext, ctx => ctx.filters),
          disabledFilterIndexes: useContextSelector(ParameterContext, ctx => ctx.disabledFilterIndexes)
        }),
        { wrapper: ParameterProviderWrapper }
      );

      expect(hook.result.current.filters).toEqual([filter]);
      expect(hook.result.current.disabledFilterIndexes).toEqual([0]);
      await waitFor(() => {
        expectSearchRequest({
          query: DEFAULT_QUERY,
          filters: expect.not.arrayContaining([filter])
        });
      });
    });

    it('gives an immutable marker-only URL navigation precedence over a debounced query update', async () => {
      mockSearchParams.append('filter', 'filter:a');
      mockSearchParams.append('filter', 'filter:b');
      mockSearchParams.set('query', 'incoming query');
      mockLocation.search = `?${mockSearchParams.toString()}`;

      const writes: string[] = [];
      const snapshots: URLSearchParams[] = [];
      vi.mocked(useSearchParams).mockImplementation(() => {
        const snapshot = new URLSearchParams(mockLocation.search);
        snapshots.push(snapshot);
        const setParamsForSnapshot = nextParams => {
          const next = typeof nextParams === 'function' ? nextParams(snapshot) : nextParams;
          writes.push(new URLSearchParams(next).toString());
        };
        return [snapshot, setParamsForSnapshot] as any;
      });

      const hook = renderHook(
        () => ({
          query: useContextSelector(ParameterContext, ctx => ctx.query),
          filters: useContextSelector(ParameterContext, ctx => ctx.filters),
          disabledFilterIndexes: useContextSelector(ParameterContext, ctx => ctx.disabledFilterIndexes),
          setQuery: useContextSelector(ParameterContext, ctx => ctx.setQuery),
          getFilters: useContextSelector(RecordSearchContext, ctx => ctx.getFilters)
        }),
        { wrapper: ParameterProviderWrapper }
      );

      act(() => hook.result.current.setQuery('local query'));
      const incomingUrl = new URLSearchParams(mockLocation.search);
      incomingUrl.append('disabled_filter', 'filter:a');
      mockLocation.search = `?${incomingUrl.toString()}`;

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 150));
      });

      expect(hook.result.current.query).toBe('incoming query');
      expect(hook.result.current.filters).toEqual(['filter:a', 'filter:b']);
      expect(hook.result.current.disabledFilterIndexes).toEqual([0]);
      const effectiveFilters = await hook.result.current.getFilters();
      expect(effectiveFilters).toContain('filter:b');
      expect(effectiveFilters).not.toContain('filter:a');
      expect(writes).toEqual([]);

      await waitFor(() => {
        expectSearchRequest({
          query: 'incoming query',
          filters: expect.arrayContaining(['filter:b'])
        });
        expectSearchRequest({ filters: expect.not.arrayContaining(['filter:a']) });
      });

      hook.rerender();
      hook.rerender();
      expect(mockLocation.search).toBe(`?${incomingUrl.toString()}`);
      expect(hook.result.current.disabledFilterIndexes).toEqual([0]);
      expect(writes).toEqual([]);
      expect(snapshots.length).toBeGreaterThan(1);
      expect(snapshots[snapshots.length - 1]).not.toBe(snapshots[snapshots.length - 2]);
    });

    it('keeps the surviving disabled filter excluded after an edit creates duplicate definitions', async () => {
      mockSearchParams.append('filter', 'filter:a');
      mockSearchParams.append('filter', 'filter:b');
      mockLocation.search = '?filter=filter%3Aa&filter=filter%3Ab';
      makeMockSetParamsUpdateUrl();

      const hook = renderHook(
        () => ({
          filters: useContextSelector(ParameterContext, ctx => ctx.filters),
          disabledFilterIndexes: useContextSelector(ParameterContext, ctx => ctx.disabledFilterIndexes),
          disableFilter: useContextSelector(ParameterContext, ctx => ctx.disableFilter),
          setFilter: useContextSelector(ParameterContext, ctx => ctx.setFilter),
          search: useContextSelector(RecordSearchContext, ctx => ctx.search)
        }),
        { wrapper: ParameterProviderWrapper }
      );

      await act(async () => {
        hook.result.current.disableFilter(0);
        hook.result.current.disableFilter(1);
        hook.result.current.setFilter(0, 'filter:b');
      });
      await act(async () => hook.rerender());

      await waitFor(() => {
        expect(hook.result.current.filters).toEqual(['filter:b']);
        expect(hook.result.current.disabledFilterIndexes).toEqual([0]);
        expect(mockSearchParams.getAll('filter')).toEqual(['filter:b']);
        expect(mockSearchParams.getAll('disabled_filter')).toEqual(['filter:b']);
      });

      vi.mocked(hpost).mockClear();
      act(() => {
        hook.result.current.search();
      });

      await waitFor(() => {
        expectSearchRequest({ filters: expect.not.arrayContaining(['filter:b']) });
      });
    });

    it('keeps a duplicate filter effective when any collapsed occurrence was enabled', async () => {
      mockSearchParams.append('filter', 'filter:a');
      mockSearchParams.append('filter', 'filter:b');
      mockLocation.search = '?filter=filter%3Aa&filter=filter%3Ab';
      makeMockSetParamsUpdateUrl();

      const hook = renderHook(
        () => ({
          filters: useContextSelector(ParameterContext, ctx => ctx.filters),
          disabledFilterIndexes: useContextSelector(ParameterContext, ctx => ctx.disabledFilterIndexes),
          disableFilter: useContextSelector(ParameterContext, ctx => ctx.disableFilter),
          setFilter: useContextSelector(ParameterContext, ctx => ctx.setFilter),
          getFilters: useContextSelector(RecordSearchContext, ctx => ctx.getFilters),
          search: useContextSelector(RecordSearchContext, ctx => ctx.search)
        }),
        { wrapper: ParameterProviderWrapper }
      );

      await act(async () => {
        hook.result.current.disableFilter(0);
        hook.result.current.setFilter(0, 'filter:b');
      });
      await act(async () => hook.rerender());

      await waitFor(() => {
        expect(hook.result.current.filters).toEqual(['filter:b']);
        expect(hook.result.current.disabledFilterIndexes).toEqual([]);
        expect(mockSearchParams.getAll('filter')).toEqual(['filter:b']);
        expect(mockSearchParams.getAll('disabled_filter')).toEqual([]);
      });

      expect(await hook.result.current.getFilters()).toContain('filter:b');

      vi.mocked(hpost).mockClear();
      act(() => {
        hook.result.current.search();
      });

      await waitFor(() => {
        expectSearchRequest({ filters: expect.arrayContaining(['filter:b']) });
      });
    });

    it('should perform a search and update response', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            search: ctx.search,
            searching: ctx.searching,
            response: ctx.response,
            error: ctx.error
          })),
        { wrapper: Wrapper }
      );

      act(() => {
        hook.result.current.search('test query');
      });

      await waitFor(() => {
        expectSearchRequest({ query: expect.stringContaining('test query') });
      });
    });

    it('should set searching state during search', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            search: ctx.search,
            searching: ctx.searching
          })),
        { wrapper: Wrapper }
      );

      expect(hook.result.current.searching).toBe(false);

      let res: any;
      vi.mocked(hpost).mockReturnValue(new Promise(_res => (res = _res)));

      act(() => {
        hook.result.current.search('test query');
      });

      hook.rerender();

      // Searching should be true immediately after calling search
      await waitFor(() => {
        expect(hook.result.current.searching).toBe(true);
      });

      res({
        items: [{ howler: { id: 'hit1' } }],
        offset: 0,
        rows: 1,
        total: 10
      });

      hook.rerender();

      // Searching should be true immediately after calling search
      await waitFor(() => {
        expect(hook.result.current.searching).toBe(false);
      });
    });

    it('should handle search errors', async () => {
      vi.mocked(hpost).mockRejectedValueOnce(new Error('Search failed'));

      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            search: ctx.search,
            error: ctx.error,
            searching: ctx.searching
          })),
        { wrapper: Wrapper }
      );

      act(() => {
        hook.result.current.search('test query');
      });

      await waitFor(() => {
        expect(hook.result.current.error).toBe('Search failed');
        expect(hook.result.current.searching).toBe(false);
      });
    });

    it('should append results when appendResults is true', async () => {
      const mockResponse = {
        items: [{ howler: { id: 'hit1' } }],
        offset: 0,
        rows: 1,
        total: 10
      };

      vi.mocked(hpost).mockResolvedValueOnce(mockResponse as any);

      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            search: ctx.search,
            response: ctx.response
          })),
        { wrapper: Wrapper }
      );

      // First search
      act(() => {
        hook.result.current.search('test query');
      });

      await waitFor(() => {
        expect(hook.result.current.response).toBeDefined();
        expect(hook.result.current.response).not.toBeNull();
      });

      // Mock second response
      vi.mocked(hpost).mockResolvedValueOnce({
        items: [{ howler: { id: 'hit2' } }],
        offset: 1,
        rows: 1,
        total: 10
      } as any);

      // Append results
      act(() => {
        hook.result.current.search('test query', true);
      });

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current.response?.items.length).toBe(2);
      });
    });

    it('should not crash when appendResults is true but response is null', async () => {
      const mockResponse = {
        items: [{ howler: { id: 'hit1' } }],
        offset: 0,
        rows: 1,
        total: 10
      };

      vi.mocked(hpost).mockResolvedValueOnce(mockResponse as any);

      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            search: ctx.search,
            response: ctx.response
          })),
        { wrapper: Wrapper }
      );

      // response is null — call search with appendResults=true directly
      act(() => {
        hook.result.current.search('test query', true);
      });

      await waitFor(() => {
        expect(hook.result.current.response).not.toBeNull();
        expect(hook.result.current.response?.items).toHaveLength(1);
        expect(hook.result.current.response?.items[0].howler.id).toBe('hit1');
      });
    });

    it('should apply date range filter from span', async () => {
      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

      act(() => {
        hook.result.current('test query');
      });

      await waitFor(() => {
        expectSearchRequest({
          filters: expect.arrayContaining([expect.stringContaining('event.created:')])
        });
      });
    });

    it('should apply custom date range when span is custom', async () => {
      mockParameterContext.span = 'date.range.custom';
      mockParameterContext.startDate = '2025-01-01';
      mockParameterContext.endDate = '2025-12-31';

      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

      act(() => {
        hook.result.current('test query');
      });

      await waitFor(() => {
        expectSearchRequest({
          filters: expect.arrayContaining([expect.stringContaining('event.created:')])
        });
      });
    });

    it('should exclude filters ending with * from search', async () => {
      mockParameterContext.filters = ['status:open', 'howler.escalation:*'];

      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

      act(() => {
        hook.result.current('test query');
      });

      await waitFor(() => {
        expectSearchRequest({
          filters: expect.not.arrayContaining([expect.stringContaining('howler.escalation:*')])
        });
      });
    });

    it('should forward positive and negative grouped filters without changing their clauses', async () => {
      mockParameterContext.filters = [
        'event.provider:"azure"',
        '-howler.outline.indicators:("a" OR "b")',
        'event.provider:"\\*"',
        '-event.provider:"\\*"'
      ];

      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

      act(() => {
        hook.result.current('test query');
      });

      await waitFor(() => {
        const searchRequest = vi.mocked(hpost).mock.calls.find(([url]) => url === '/api/v2/search/hit')?.[1];

        expect(searchRequest).toEqual(
          expect.objectContaining({
            filters: expect.arrayContaining([
              'event.provider:"azure"',
              '-howler.outline.indicators:("a" OR "b")',
              'event.provider:"\\*"',
              '-event.provider:"\\*"'
            ])
          })
        );
      });
    });

    it('should reset offset if response total is less than current offset', async () => {
      mockParameterContext.offset = 100;

      vi.mocked(hpost).mockResolvedValueOnce({
        items: [],
        offset: 0,
        rows: 0,
        total: 50
      } as any);

      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            search: ctx.search
          })),
        { wrapper: Wrapper }
      );

      act(() => {
        hook.result.current.search('test query');
      });

      hook.rerender();

      await waitFor(() => {
        expect(mockParameterContext.offset).toBe(0);
      });
    });

    it('should not search when sort or span is null', async () => {
      mockParameterContext.sort = null;
      mockParameterContext.span = null;

      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

      act(() => {
        hook.result.current('test query');
      });

      // Should not make API call
      await waitFor(() => {
        expect(hpost).not.toHaveBeenCalled();
      });
    });
  });

  describe('automatic search on parameter changes', () => {
    it('should trigger search when filters change', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            response: ctx.response
          })),
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(hpost).toHaveBeenCalled();
      });

      vi.mocked(hpost).mockClear();

      // Change filters via ParameterContext
      mockParameterContext.filters = [...mockParameterContext.filters, 'howler.status:open'];

      hook.rerender();

      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalled();
        },
        { timeout: 2000 }
      );
    });

    it('should refresh results when disabling the last effective filter', async () => {
      mockParameterContext.query = DEFAULT_QUERY;
      mockParameterContext.views = [];
      mockParameterContext.filters = ['howler.status:open'];

      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), { wrapper: Wrapper });

      await waitFor(() => {
        expectSearchRequest({ filters: expect.arrayContaining(['howler.status:open']) });
      });

      vi.mocked(hpost).mockClear();
      mockParameterContext.disabledFilterIndexes = [0];
      hook.rerender();

      await waitFor(() => {
        expectSearchRequest({
          query: DEFAULT_QUERY,
          filters: expect.not.arrayContaining(['howler.status:open'])
        });
      });

      vi.mocked(hpost).mockClear();
      mockParameterContext.disabledFilterIndexes = [];
      hook.rerender();

      await waitFor(() => {
        expectSearchRequest({
          query: DEFAULT_QUERY,
          filters: expect.arrayContaining(['howler.status:open'])
        });
      });
    });

    it('does not search when only a disabled positive wildcard placeholder remains', async () => {
      mockParameterContext.query = DEFAULT_QUERY;
      mockParameterContext.views = [];
      mockParameterContext.filters = ['howler.assessment:*'];
      mockParameterContext.disabledFilterIndexes = [0];

      renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), { wrapper: Wrapper });

      await new Promise(resolve => setTimeout(resolve, 600));
      expect(hpost).not.toHaveBeenCalled();
    });

    it('should not trigger search when query is DEFAULT_QUERY', async () => {
      mockParameterContext.query = DEFAULT_QUERY;

      renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), { wrapper: Wrapper });

      await waitFor(() => {
        expect(hpost).not.toHaveBeenCalled();
      });
    });

    it('should not trigger search when span is custom but dates are missing', async () => {
      renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), { wrapper: Wrapper });

      await waitFor(() => {
        expect(hpost).not.toHaveBeenCalled();
      });
    });
  });

  describe('useRecordSearchContextSelector', () => {
    it('should allow selecting specific values from context', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(RecordSearchContext, ctx => ({
            searching: ctx.searching,
            error: ctx.error
          })),
        { wrapper: Wrapper }
      );

      expect(hook.result.current.searching).toBe(false);
      expect(hook.result.current.error).toBeNull();
    });
  });

  describe('edge cases', () => {
    it('should handle concurrent search calls with throttling', async () => {
      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

      // Make multiple rapid calls
      act(() => {
        hook.result.current('query1');
        hook.result.current('query2');
        hook.result.current('query3');
      });

      // Should only call API once due to throttling
      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalledTimes(1);
        },
        { timeout: 2000 }
      );
    });

    it('should clear response when query becomes DEFAULT_QUERY without viewId', async () => {
      const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), { wrapper: Wrapper });

      await waitFor(
        () => {
          expect(hook.result.current).toBeDefined();
        },
        { timeout: 2000 }
      );

      // Change to default query
      mockParameterContext.query = DEFAULT_QUERY;

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current).toBeNull();
      });
    });
  });

  describe('multiple views support', () => {
    describe('disabled views', () => {
      beforeEach(() => {
        mockViewContext.getCurrentViews = vi.fn(async ({ views = [], ignoreParams = false } = {}) => {
          const ids = ignoreParams ? views : [...new Set([...views, ...mockSearchParams.getAll('view')])];
          return ids.map(id => ({ view_id: id, query: `howler.analytic:${id}` }));
        });
      });

      it('restores disabled views from copied links without reintroducing them from URL params', async () => {
        mockSearchParams.append('view', 'disabled_view');
        mockSearchParams.append('view', 'enabled_view');
        mockSearchParams.append('disabled_view', 'disabled_view');
        mockSearchParams.append('filter', '-howler.assessment:*');
        mockSearchParams.set('disabled_index', 'hit');
        mockLocation.search = `?${mockSearchParams.toString()}`;

        const hook = renderHook(
          () => ({
            views: useContextSelector(ParameterContext, ctx => ctx.views),
            disabledViewIndexes: useContextSelector(ParameterContext, ctx => ctx.disabledViewIndexes)
          }),
          { wrapper: ParameterProviderWrapper }
        );

        expect(hook.result.current.views).toEqual(['disabled_view', 'enabled_view']);
        expect(hook.result.current.disabledViewIndexes).toEqual([0]);
        await waitFor(() => {
          expectSearchRequest({
            query: DEFAULT_QUERY,
            filters: ['-howler.assessment:*', 'event.created:[now-1M TO now]', 'howler.analytic:enabled_view']
          });
        });
        expect(mockViewContext.getCurrentViews).toHaveBeenCalledWith({ views: ['enabled_view'], ignoreParams: true });
      });

      it('searches with only disabled views and does not inject or resolve a default view', async () => {
        mockViewContext.defaultView = 'default_view';
        mockSearchParams.append('view', 'disabled_view');
        mockSearchParams.append('disabled_view', 'disabled_view');
        mockLocation.search = `?${mockSearchParams.toString()}`;
        makeMockSetParamsUpdateUrl();

        renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), {
          wrapper: ParameterProviderWrapper
        });

        await waitFor(() => {
          expectSearchRequest({ query: DEFAULT_QUERY, filters: ['event.created:[now-1M TO now]'] });
        });
        expect(mockViewContext.getCurrentViews).not.toHaveBeenCalled();
        expect(mockSearchParams.getAll('view')).toEqual(['disabled_view']);
        expect(mockSearchParams.getAll('disabled_view')).toEqual(['disabled_view']);
      });

      it('refreshes the effective search when the last view is disabled and re-enabled', async () => {
        mockSearchParams.append('view', 'first_view');
        mockLocation.search = `?${mockSearchParams.toString()}`;
        makeMockSetParamsUpdateUrl();
        const hook = renderHook(
          () => ({
            enableView: useContextSelector(ParameterContext, ctx => ctx.enableView),
            disableView: useContextSelector(ParameterContext, ctx => ctx.disableView)
          }),
          { wrapper: ParameterProviderWrapper }
        );

        await waitFor(() => {
          expectSearchRequest({ filters: expect.arrayContaining(['howler.analytic:first_view']) });
        });
        vi.mocked(hpost).mockClear();
        await act(async () => hook.result.current.disableView(0));
        hook.rerender();
        await waitFor(() => {
          expectSearchRequest({ filters: ['event.created:[now-1M TO now]'] });
        });

        vi.mocked(hpost).mockClear();
        await act(async () => hook.result.current.enableView(0));
        hook.rerender();
        await waitFor(() => {
          expectSearchRequest({ filters: expect.arrayContaining(['howler.analytic:first_view']) });
        });
        expect(mockSearchParams.getAll('view')).toEqual(['first_view']);
        expect(mockSearchParams.getAll('disabled_view')).toEqual([]);
      });
    });

    describe('AND logic for multiple view queries', () => {
      it('should combine two view queries with AND logic', async () => {
        mockParameterContext.views = ['view_1', 'view_2'];

        mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
          { view_id: 'view_1', query: 'howler.status:open' },
          { view_id: 'view_2', query: 'howler.priority:high' }
        ]);

        const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

        act(() => {
          hook.result.current('test query');
        });

        await waitFor(() => {
          expectSearchRequest({
            query: 'test query',
            filters: expect.arrayContaining(['howler.status:open', 'howler.priority:high'])
          });
        });
      });

      it('should combine three view queries with AND logic', async () => {
        mockParameterContext.views = ['view_1', 'view_2', 'view_3'];

        mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
          { view_id: 'view_1', query: 'howler.status:open' },
          { view_id: 'view_2', query: 'howler.priority:high' },
          { view_id: 'view_3', query: 'howler.analytic:sigma' }
        ]);

        const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

        act(() => {
          hook.result.current('test query');
        });

        await waitFor(() => {
          expectSearchRequest({
            query: 'test query',
            filters: [
              'event.created:[now-1w TO now]',
              'howler.status:open',
              'howler.priority:high',
              'howler.analytic:sigma'
            ]
          });
        });
      });
    });

    describe('default view URL injection', () => {
      it('should inject default view into URL when no views and not on /views route', async () => {
        mockViewContext.defaultView = 'default_view_id';
        mockLocation.pathname = '/search';
        mockParameterContext.views = [];

        const mockSearchParams = new URLSearchParams();
        vi.mocked(useSearchParams).mockReturnValue([mockSearchParams, mockSetParams]);

        renderHook(() => useContextSelector(RecordSearchContext, () => {}), { wrapper: Wrapper });

        await waitFor(() => {
          expect(mockParameterContext.addView).toBeCalledWith('default_view_id');
        });
      });

      it('should not inject default view when views already present', async () => {
        mockViewContext.defaultView = 'default_view_id';
        mockLocation.pathname = '/search';
        mockParameterContext.views = ['existing_view'];

        const mockSearchParams = new URLSearchParams();
        mockSearchParams.append('view', 'existing_view');
        vi.mocked(useSearchParams).mockReturnValue([mockSearchParams, mockSetParams]);

        renderHook(() => useContextSelector(RecordSearchContext, () => {}), { wrapper: Wrapper });

        await waitFor(() => {
          expect(mockParameterContext.addView).not.toBeCalled();
        });
      });

      it('should not inject when no default view exists', async () => {
        mockViewContext.defaultView = null;
        mockLocation.pathname = '/search';
        mockParameterContext.views = [];

        const mockSearchParams = new URLSearchParams();
        vi.mocked(useSearchParams).mockReturnValue([mockSearchParams, mockSetParams]);

        renderHook(() => useContextSelector(RecordSearchContext, () => {}), { wrapper: Wrapper });

        await waitFor(() => {
          expect(mockSetParams).not.toHaveBeenCalled();
        });
      });
    });

    describe('invalid view IDs', () => {
      it('should not break when view ID does not exist', async () => {
        mockParameterContext.views = ['non_existent_view'];

        mockViewContext.getCurrentViews = vi.fn(() => Promise.resolve([null]));

        const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

        act(() => {
          hook.result.current('test query');
        });

        await waitFor(
          () => {
            expectSearchRequest({
              query: expect.stringContaining('test query'),
              filters: ['event.created:[now-1w TO now]']
            });
          },
          { timeout: 2000 }
        );
      });

      it('should skip null views and combine valid ones', async () => {
        mockParameterContext.views = ['view_1', 'invalid_view', 'view_2'];

        mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
          { view_id: 'view_1', query: 'howler.status:open' },
          { view_id: 'view_2', query: 'howler.priority:high' }
        ]);

        const hook = renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.search), { wrapper: Wrapper });

        act(() => {
          hook.result.current('test query');
        });

        await waitFor(() => {
          expectSearchRequest({
            query: 'test query',
            filters: ['event.created:[now-1w TO now]', 'howler.status:open', 'howler.priority:high']
          });
        });
      });
    });

    describe('automatic search triggering', () => {
      it('should not trigger search when views is empty and query is DEFAULT_QUERY', async () => {
        mockParameterContext.query = DEFAULT_QUERY;
        mockParameterContext.views = [];

        renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), { wrapper: Wrapper });

        await waitFor(() => {
          expect(hpost).not.toHaveBeenCalled();
        });
      });

      it('should trigger search when views.length > 0 even with DEFAULT_QUERY', async () => {
        mockParameterContext.query = DEFAULT_QUERY;
        mockParameterContext.views = ['view_1'];

        renderHook(() => useContextSelector(RecordSearchContext, ctx => ctx.response), { wrapper: Wrapper });

        await waitFor(() => {
          expect(hpost).toHaveBeenCalled();
        });
      });
    });
  });
});
