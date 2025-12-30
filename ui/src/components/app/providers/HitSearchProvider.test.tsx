import { act, renderHook, waitFor } from '@testing-library/react';
import { hpost } from 'api';
import { createContext, useContext } from 'react';
import MockLocalStorage from 'tests/MockLocalStorage';
import { useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY, MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';
import { HitContext, type HitContextType } from './HitProvider';
import HitSearchProvider, { HitSearchContext } from './HitSearchProvider';
import { ParameterContext, type ParameterContextType } from './ParameterProvider';
import { ViewContext, type ViewContextType } from './ViewProvider';

const mockLocation = { pathname: '/hits', search: '' };
const mockParams = { id: undefined };
let mockSearchParams = new URLSearchParams();
const mockSetParams = vi.fn();

vi.mock('api', { spy: true });
vi.mock('react-router-dom', () => ({
  useLocation: vi.fn(() => mockLocation),
  useParams: vi.fn(() => mockParams),
  useSearchParams: vi.fn(() => [mockSearchParams, mockSetParams])
}));

vi.mock('use-context-selector', async () => {
  const actual = await vi.importActual('use-context-selector');
  return {
    ...actual,
    createContext,
    useContextSelector: (_context: any, selector: any) => {
      return selector(useContext(_context));
    }
  };
});

const mockLocalStorage: Storage = new MockLocalStorage() as any;
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true
});

const mockViewContext: Partial<ViewContextType> = {
  getCurrentView: ({ viewId }) => Promise.resolve({ view_id: viewId, query: 'howler.id:*' })
};
const mockParameterContext: Partial<ParameterContextType> = {
  filters: [],
  span: 'span',
  sort: 'sort',
  query: 'howler.id:*',
  setQuery: query => (mockParameterContext.query = query),
  offset: 0
};
const mockHitContext: Partial<HitContextType> = {
  hits: {},
  loadHits: hits => {
    mockHitContext.hits = {
      ...mockHitContext.hits,
      ...Object.fromEntries(hits.map(hit => [hit.howler.id, hit]))
    };
  }
};

const Wrapper = ({ children }) => {
  return (
    <ViewContext.Provider value={mockViewContext as any}>
      <ParameterContext.Provider value={mockParameterContext as any}>
        <HitContext.Provider value={mockHitContext as any}>
          <HitSearchProvider>{children}</HitSearchProvider>
        </HitContext.Provider>
      </ParameterContext.Provider>
    </ViewContext.Provider>
  );
};

beforeEach(() => {
  mockLocalStorage.clear();
  mockSearchParams = new URLSearchParams();
  mockSetParams.mockClear();
  mockLocation.pathname = '/hits';
  mockLocation.search = '';
  mockParams.id = undefined;
  vi.mocked(hpost).mockClear();
});

describe('HitSearchContext', () => {
  it('should initialize with default values', async () => {
    const hook = await act(async () =>
      renderHook(
        () =>
          useContextSelector(HitSearchContext, ctx => ({
            displayType: ctx.displayType,
            searching: ctx.searching,
            error: ctx.error,
            response: ctx.response,
            viewId: ctx.viewId,
            bundleId: ctx.bundleId,
            fzfSearch: ctx.fzfSearch
          })),
        { wrapper: Wrapper }
      )
    );

    expect(hook.result.current.displayType).toBe('list');
    expect(hook.result.current.searching).toBe(false);
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.response).toBeNull();
    expect(hook.result.current.viewId).toBeNull();
    expect(hook.result.current.bundleId).toBeNull();
    expect(hook.result.current.fzfSearch).toBe(false);
  });

  it('should set viewId when on views route', async () => {
    mockLocation.pathname = '/views/test_view_id';
    mockParams.id = 'test_view_id';

    const hook = await act(async () =>
      renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.viewId), { wrapper: Wrapper })
    );

    expect(hook.result.current).toBe('test_view_id');
  });

  it('should set bundleId when on bundles route', async () => {
    mockLocation.pathname = '/bundles/test_bundle_id';
    mockParams.id = 'test_bundle_id';

    const hook = await act(async () =>
      renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.bundleId), { wrapper: Wrapper })
    );

    expect(hook.result.current).toBe('test_bundle_id');
  });

  it('should initialize queryHistory from localStorage', async () => {
    const mockHistory = { 'test:query': new Date().toISOString() };
    mockLocalStorage.setItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.QUERY_HISTORY}`, JSON.stringify(mockHistory));

    const hook = await act(async () =>
      renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.queryHistory), { wrapper: Wrapper })
    );

    expect(hook.result.current).toEqual(mockHistory);
  });

  describe('setDisplayType', () => {
    it('should update display type', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              displayType: ctx.displayType,
              setDisplayType: ctx.setDisplayType
            })),
          { wrapper: Wrapper }
        )
      );

      expect(hook.result.current.displayType).toBe('list');

      await act(async () => {
        hook.result.current.setDisplayType('grid');
      });

      await waitFor(() => {
        expect(hook.result.current.displayType).toBe('grid');
      });
    });
  });

  describe('setFzfSearch', () => {
    it('should update fzfSearch state', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              fzfSearch: ctx.fzfSearch,
              setFzfSearch: ctx.setFzfSearch
            })),
          { wrapper: Wrapper }
        )
      );

      expect(hook.result.current.fzfSearch).toBe(false);

      await act(async () => {
        hook.result.current.setFzfSearch(true);
      });

      await waitFor(() => {
        expect(hook.result.current.fzfSearch).toBe(true);
      });
    });
  });

  describe('setQueryHistory', () => {
    it('should update query history', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              queryHistory: ctx.queryHistory,
              setQueryHistory: ctx.setQueryHistory
            })),
          { wrapper: Wrapper }
        )
      );

      const newHistory = { 'new:query': new Date().toISOString() };

      await act(async () => {
        hook.result.current.setQueryHistory(newHistory);
      });

      await waitFor(() => {
        expect(hook.result.current.queryHistory).toEqual(newHistory);
      });
    });
  });

  describe('search', () => {
    it('should perform a search and update response', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              search: ctx.search,
              searching: ctx.searching,
              response: ctx.response,
              error: ctx.error
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.search('test query');
      });

      await waitFor(() => {
        expect(hpost).toHaveBeenCalledWith(
          '/api/v1/search/hit',
          expect.objectContaining({
            query: expect.stringContaining('test query')
          })
        );
      });
    });

    it('should set searching state during search', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              search: ctx.search,
              searching: ctx.searching
            })),
          { wrapper: Wrapper }
        )
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

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              search: ctx.search,
              error: ctx.error,
              searching: ctx.searching
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.search('test query');
      });

      await waitFor(
        () => {
          expect(hook.result.current.error).toBe('Search failed');
          expect(hook.result.current.searching).toBe(false);
        },
        { timeout: 2000 }
      );
    });

    it('should append results when appendResults is true', async () => {
      const mockResponse = {
        items: [{ howler: { id: 'hit1' } }],
        offset: 0,
        rows: 1,
        total: 10
      };

      vi.mocked(hpost).mockResolvedValueOnce(mockResponse as any);

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              search: ctx.search,
              response: ctx.response
            })),
          { wrapper: Wrapper }
        )
      );

      // First search
      await act(async () => {
        hook.result.current.search('test query');
      });

      await waitFor(
        () => {
          expect(hook.result.current.response).toBeDefined();
          expect(hook.result.current.response).not.toBeNull();
        },
        { timeout: 2000 }
      );

      // Mock second response
      vi.mocked(hpost).mockResolvedValueOnce({
        items: [{ howler: { id: 'hit2' } }],
        offset: 1,
        rows: 1,
        total: 10
      } as any);

      // Append results
      await act(async () => {
        hook.result.current.search('test query', true);
      });

      hook.rerender();

      await waitFor(
        () => {
          expect(hook.result.current.response?.items.length).toBe(2);
        },
        { timeout: 2000 }
      );
    });

    it('should include bundle filter when on bundles route', async () => {
      mockLocation.pathname = '/bundles/test_bundle_id';
      mockParams.id = 'test_bundle_id';

      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.search), { wrapper: Wrapper })
      );

      await act(async () => {
        hook.result.current('test query');
      });

      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalledWith(
            '/api/v1/search/hit',
            expect.objectContaining({
              query: expect.stringContaining('howler.bundles:test_bundle_id')
            })
          );
        },
        { timeout: 2000 }
      );
    });

    it('should apply date range filter from span', async () => {
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.1.week'
      });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.search), { wrapper: Wrapper })
      );

      await act(async () => {
        hook.result.current('test query');
      });

      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalledWith(
            '/api/v1/search/hit',
            expect.objectContaining({
              filters: expect.arrayContaining([expect.stringContaining('event.created:')])
            })
          );
        },
        { timeout: 2000 }
      );
    });

    it('should apply custom date range when span is custom', async () => {
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.custom',
        start_date: '2025-01-01',
        end_date: '2025-12-31'
      });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.search), { wrapper: Wrapper })
      );

      await act(async () => {
        hook.result.current('test query');
      });

      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalledWith(
            '/api/v1/search/hit',
            expect.objectContaining({
              filters: expect.arrayContaining([expect.stringContaining('event.created:')])
            })
          );
        },
        { timeout: 2000 }
      );
    });

    it('should exclude filters ending with * from search', async () => {
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.1.month'
      });
      mockSearchParams.append('filter', 'status:open');
      mockSearchParams.append('filter', 'howler.escalation:*');

      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.search), { wrapper: Wrapper })
      );

      await act(async () => {
        hook.result.current('test query');
      });

      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalledWith(
            '/api/v1/search/hit',
            expect.objectContaining({
              filters: expect.not.arrayContaining([expect.stringContaining('howler.escalation:*')])
            })
          );
        },
        { timeout: 2000 }
      );
    });

    it('should reset offset if response total is less than current offset', async () => {
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.1.month',
        offset: '100'
      });

      vi.mocked(hpost).mockResolvedValueOnce({
        items: [],
        offset: 0,
        rows: 0,
        total: 50
      } as any);

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              search: ctx.search
            })),
          { wrapper: Wrapper }
        )
      );

      const parameterHook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.offset), { wrapper: Wrapper })
      );

      await act(async () => {
        hook.result.current.search('test query');
      });

      await waitFor(
        () => {
          expect(parameterHook.result.current).toBe(0);
        },
        { timeout: 2000 }
      );
    });

    it('should change language to woof when query is "woof!"', async () => {
      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.search), { wrapper: Wrapper })
      );

      await act(async () => {
        hook.result.current('woof!');
      });

      // Should not make API call
      expect(hpost).not.toHaveBeenCalled();
    });

    it('should not search when sort or span is null', async () => {
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY
      });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.search), { wrapper: Wrapper })
      );

      await act(async () => {
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
      mockSearchParams = new URLSearchParams({
        query: 'initial query',
        sort: 'event.created desc',
        span: 'date.range.1.month'
      });

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              response: ctx.response
            })),
          { wrapper: Wrapper }
        )
      );

      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalled();
        },
        { timeout: 2000 }
      );

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

    it('should not trigger search when query is DEFAULT_QUERY and no viewId or bundleId', async () => {
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.1.month'
      });

      await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.response), { wrapper: Wrapper })
      );

      await waitFor(() => {
        expect(hpost).not.toHaveBeenCalled();
      });
    });

    it('should trigger search when viewId is present', async () => {
      mockLocation.pathname = '/views/test_view_id';
      mockParams.id = 'test_view_id';
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.1.month'
      });

      await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.response), { wrapper: Wrapper })
      );

      await waitFor(
        () => {
          expect(hpost).toHaveBeenCalled();
        },
        { timeout: 2000 }
      );
    });

    it('should not trigger search when span is custom but dates are missing', async () => {
      mockSearchParams = new URLSearchParams({
        query: 'test query',
        sort: 'event.created desc',
        span: 'date.range.custom'
      });

      await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.response), { wrapper: Wrapper })
      );

      await waitFor(() => {
        expect(hpost).not.toHaveBeenCalled();
      });
    });
  });

  describe('useHitSearchContextSelector', () => {
    it('should allow selecting specific values from context', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(HitSearchContext, ctx => ({
              searching: ctx.searching,
              error: ctx.error
            })),
          { wrapper: Wrapper }
        )
      );

      expect(hook.result.current.searching).toBe(false);
      expect(hook.result.current.error).toBeNull();
    });
  });

  describe('edge cases', () => {
    it('should handle concurrent search calls with throttling', async () => {
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.1.month'
      });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.search), { wrapper: Wrapper })
      );

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

    it('should clear response when query becomes DEFAULT_QUERY without viewId or bundleId', async () => {
      mockSearchParams = new URLSearchParams({
        query: 'specific query',
        sort: 'event.created desc',
        span: 'date.range.1.month'
      });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(HitSearchContext, ctx => ctx.response), { wrapper: Wrapper })
      );

      await waitFor(
        () => {
          expect(hook.result.current).toBeDefined();
        },
        { timeout: 2000 }
      );

      // Change to default query
      mockSearchParams = new URLSearchParams({
        query: DEFAULT_QUERY,
        sort: 'event.created desc',
        span: 'date.range.1.month'
      });
      mockLocation.search = `?query=${DEFAULT_QUERY}&sort=event.created%20desc&span=date.range.1.month`;

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current).toBeNull();
      });
    });
  });
});
