import { act, renderHook, waitFor } from '@testing-library/react';
import { useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY } from 'utils/constants';
import ParameterProvider, { ParameterContext } from './ParameterProvider';

// Mock dependencies
const mockSetParams = vi.fn();
const mockLocation = { pathname: '/hits', search: '' };
const mockParams = { id: undefined };

let mockSearchParams = new URLSearchParams();

vi.mock('react-router-dom', () => ({
  useLocation: vi.fn(() => mockLocation),
  useParams: vi.fn(() => mockParams),
  useSearchParams: vi.fn(() => [mockSearchParams, mockSetParams])
}));

const Wrapper = ({ children }) => {
  return <ParameterProvider>{children}</ParameterProvider>;
};

beforeEach(() => {
  mockSearchParams = new URLSearchParams();
  mockSetParams.mockClear();
  mockLocation.pathname = '/hits';
  mockLocation.search = '';
  mockParams.id = undefined;
});

describe('ParameterContext', () => {
  it('should initialize with default values when no URL params are present', async () => {
    const hook = await act(async () =>
      renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            query: ctx.query,
            sort: ctx.sort,
            span: ctx.span,
            offset: ctx.offset,
            trackTotalHits: ctx.trackTotalHits
          })),
        { wrapper: Wrapper }
      )
    );

    expect(hook.result.current.query).toBe(DEFAULT_QUERY);
    expect(hook.result.current.sort).toBe('event.created desc');
    expect(hook.result.current.span).toBe('date.range.1.month');
    expect(hook.result.current.offset).toBe(0);
    expect(hook.result.current.trackTotalHits).toBe(false);
  });

  it('should initialize with values from URL params', async () => {
    mockSearchParams = new URLSearchParams({
      query: 'test query',
      sort: 'test.field asc',
      span: 'date.range.1.week',
      offset: '25',
      selected: 'test_id',
      filter: 'status:open',
      track_total_hits: 'true'
    });

    const hook = await act(async () =>
      renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            query: ctx.query,
            sort: ctx.sort,
            span: ctx.span,
            offset: ctx.offset,
            selected: ctx.selected,
            filters: ctx.filters,
            trackTotalHits: ctx.trackTotalHits
          })),
        { wrapper: Wrapper }
      )
    );

    expect(hook.result.current.query).toBe('test query');
    expect(hook.result.current.sort).toBe('test.field asc');
    expect(hook.result.current.span).toBe('date.range.1.week');
    expect(hook.result.current.offset).toBe(25);
    expect(hook.result.current.selected).toBe('test_id');
    expect(hook.result.current.filters).toEqual(['status:open']);
    expect(hook.result.current.trackTotalHits).toBe(true);
  });

  it('should handle custom date span with start and end dates', async () => {
    mockSearchParams = new URLSearchParams({
      span: 'date.range.custom',
      start_date: '2025-01-01',
      end_date: '2025-12-31'
    });

    const hook = await act(async () =>
      renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            span: ctx.span,
            startDate: ctx.startDate,
            endDate: ctx.endDate
          })),
        { wrapper: Wrapper }
      )
    );

    expect(hook.result.current.span).toBe('date.range.custom');
    expect(hook.result.current.startDate).toBe('2025-01-01');
    expect(hook.result.current.endDate).toBe('2025-12-31');
  });

  describe('setQuery', () => {
    it('should update the query value', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              query: ctx.query,
              setQuery: ctx.setQuery
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setQuery('new query');
      });

      await waitFor(() => {
        expect(hook.result.current.query).toBe('new query');
      });
    });

    it('should not update if the value is the same', async () => {
      mockSearchParams = new URLSearchParams({ query: 'existing query' });

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              query: ctx.query,
              setQuery: ctx.setQuery
            })),
          { wrapper: Wrapper }
        )
      );

      const initialQuery = hook.result.current.query;

      await act(async () => {
        hook.result.current.setQuery('existing query');
      });

      expect(hook.result.current.query).toBe(initialQuery);
    });
  });

  describe('setSort', () => {
    it('should update the sort value', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              sort: ctx.sort,
              setSort: ctx.setSort
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setSort('field.name asc');
      });

      await waitFor(() => {
        expect(hook.result.current.sort).toBe('field.name asc');
      });
    });
  });

  describe('setSpan', () => {
    it('should update the span value', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              span: ctx.span,
              setSpan: ctx.setSpan
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setSpan('date.range.1.week');
      });

      await waitFor(() => {
        expect(hook.result.current.span).toBe('date.range.1.week');
      });
    });

    it('should clear startDate and endDate when span does not end with custom', async () => {
      mockSearchParams = new URLSearchParams({
        span: 'date.range.custom',
        start_date: '2025-01-01',
        end_date: '2025-12-31'
      });

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              span: ctx.span,
              startDate: ctx.startDate,
              endDate: ctx.endDate,
              setSpan: ctx.setSpan
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setSpan('date.range.1.month');
      });

      await waitFor(() => {
        expect(hook.result.current.span).toBe('date.range.1.month');
        expect(hook.result.current.startDate).toBeNull();
        expect(hook.result.current.endDate).toBeNull();
      });
    });
  });

  describe('filters (multi-filter support)', () => {
    it('should initialize with empty array when no filter params present', async () => {
      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper })
      );

      expect(hook.result.current).toEqual([]);
    });

    it('should initialize with single filter from URL', async () => {
      mockSearchParams = new URLSearchParams({ filter: 'status:open' });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper })
      );

      expect(hook.result.current).toEqual(['status:open']);
    });

    it('should initialize with multiple filters from URL', async () => {
      mockSearchParams = new URLSearchParams();
      mockSearchParams.append('filter', 'howler.escalation:hit');
      mockSearchParams.append('filter', 'howler.assignment:someuser');

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper })
      );

      expect(hook.result.current).toEqual(['howler.escalation:hit', 'howler.assignment:someuser']);
    });

    it('should preserve filter order from URL', async () => {
      mockSearchParams = new URLSearchParams();
      mockSearchParams.append('filter', 'c');
      mockSearchParams.append('filter', 'a');
      mockSearchParams.append('filter', 'b');

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper })
      );

      expect(hook.result.current).toEqual(['c', 'a', 'b']);
    });

    describe('addFilter', () => {
      it('should add a filter to empty array', async () => {
        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                addFilter: ctx.addFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.addFilter('status:open');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['status:open']);
        });
      });

      it('should append filter to existing filters', async () => {
        mockSearchParams = new URLSearchParams({ filter: 'existing:filter' });

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                addFilter: ctx.addFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.addFilter('new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing:filter', 'new:filter']);
        });
      });

      it('should allow duplicate filters', async () => {
        mockSearchParams = new URLSearchParams({ filter: 'status:open' });

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                addFilter: ctx.addFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.addFilter('status:open');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['status:open', 'status:open']);
        });
      });
    });

    describe('removeFilter', () => {
      it('should remove first matching filter', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');
        mockSearchParams.append('filter', 'filter3');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                removeFilter: ctx.removeFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.removeFilter('filter2');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['filter1', 'filter3']);
        });
      });

      it('should remove only first occurrence of duplicate filters', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'dup');
        mockSearchParams.append('filter', 'dup');
        mockSearchParams.append('filter', 'other');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                removeFilter: ctx.removeFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.removeFilter('dup');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['dup', 'other']);
        });
      });

      it('should do nothing when removing nonexistent filter', async () => {
        mockSearchParams = new URLSearchParams({ filter: 'existing' });

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                removeFilter: ctx.removeFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.removeFilter('nonexistent');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing']);
        });
      });

      it('should handle removing from empty array', async () => {
        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                removeFilter: ctx.removeFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.removeFilter('anything');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });
    });

    describe('clearFilters', () => {
      it('should clear all filters', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                clearFilters: ctx.clearFilters
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.clearFilters();
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });

      it('should be no-op when already empty', async () => {
        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                clearFilters: ctx.clearFilters
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.clearFilters();
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });
    });

    describe('setFilter', () => {
      it('should update filter at specified index', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');
        mockSearchParams.append('filter', 'filter3');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                setFilter: ctx.setFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.setFilter(1, 'updated:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['filter1', 'updated:filter', 'filter3']);
        });
      });

      it('should update filter at index 0', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'old:filter');
        mockSearchParams.append('filter', 'filter2');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                setFilter: ctx.setFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.setFilter(0, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['new:filter', 'filter2']);
        });
      });

      it('should update filter at last index', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'old:last');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                setFilter: ctx.setFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.setFilter(1, 'new:last');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['filter1', 'new:last']);
        });
      });

      it('should do nothing when index is out of bounds', async () => {
        mockSearchParams = new URLSearchParams({ filter: 'existing' });

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                setFilter: ctx.setFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.setFilter(5, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing']);
        });
      });

      it('should do nothing when index is negative', async () => {
        mockSearchParams = new URLSearchParams({ filter: 'existing' });

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                setFilter: ctx.setFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.setFilter(-1, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing']);
        });
      });

      it('should do nothing when array is empty', async () => {
        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                filters: ctx.filters,
                setFilter: ctx.setFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.setFilter(0, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });

      it('should sync updated filter to URL', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                setFilter: ctx.setFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.setFilter(0, 'updated:filter');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('filter')).toEqual(['updated:filter', 'filter2']);
        });
      });
    });

    describe('URL synchronization', () => {
      it('should sync single filter to URL as filter param', async () => {
        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                addFilter: ctx.addFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.addFilter('test:filter');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('filter')).toEqual(['test:filter']);
        });
      });

      it('should sync multiple filters to URL as multiple filter params', async () => {
        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                addFilter: ctx.addFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.addFilter('filter1');
        });

        await act(async () => {
          hook.result.current.addFilter('filter2');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('filter')).toEqual(['filter1', 'filter2']);
        });
      });

      it('should remove all filter params when filters is empty', async () => {
        mockSearchParams = new URLSearchParams();
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');

        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                clearFilters: ctx.clearFilters
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.clearFilters();
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('filter')).toEqual([]);
        });
      });

      it('should preserve filter order when syncing to URL', async () => {
        const hook = await act(async () =>
          renderHook(
            () =>
              useContextSelector(ParameterContext, ctx => ({
                addFilter: ctx.addFilter
              })),
            { wrapper: Wrapper }
          )
        );

        await act(async () => {
          hook.result.current.addFilter('z');
          hook.result.current.addFilter('a');
          hook.result.current.addFilter('m');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('filter')).toEqual(['z', 'a', 'm']);
        });
      });
    });
  });

  describe('setSelected', () => {
    it('should update the selected value', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              selected: ctx.selected,
              setSelected: ctx.setSelected
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setSelected('test_hit_id');
      });

      await waitFor(() => {
        expect(hook.result.current.selected).toBe('test_hit_id');
      });
    });

    it('should handle selected in bundle context when value is empty', async () => {
      mockLocation.pathname = '/bundles/bundle_123';
      mockParams.id = 'bundle_123';

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              selected: ctx.selected,
              setSelected: ctx.setSelected
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setSelected(null);
      });

      await waitFor(() => {
        expect(hook.result.current.selected).toBe('bundle_123');
      });
    });
  });

  describe('setOffset', () => {
    it('should update the offset with a number', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              offset: ctx.offset,
              setOffset: ctx.setOffset
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setOffset(50);
      });

      await waitFor(() => {
        expect(hook.result.current.offset).toBe(50);
      });
    });

    it('should update the offset with a string', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              offset: ctx.offset,
              setOffset: ctx.setOffset
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setOffset('100');
      });

      await waitFor(() => {
        expect(hook.result.current.offset).toBe(100);
      });
    });

    it('should handle invalid string offset by setting to 0', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              offset: ctx.offset,
              setOffset: ctx.setOffset
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setOffset('invalid');
      });

      await waitFor(() => {
        expect(hook.result.current.offset).toBe(0);
      });
    });
  });

  describe('setCustomSpan', () => {
    it('should update both startDate and endDate', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              startDate: ctx.startDate,
              endDate: ctx.endDate,
              setCustomSpan: ctx.setCustomSpan
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setCustomSpan('2025-01-01', '2025-12-31');
      });

      await waitFor(() => {
        expect(hook.result.current.startDate).toBe('2025-01-01');
        expect(hook.result.current.endDate).toBe('2025-12-31');
      });
    });
  });

  describe('URL synchronization', () => {
    it('should synchronize state changes to URL params', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              setQuery: ctx.setQuery,
              setSort: ctx.setSort
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setQuery('new query');
      });

      await waitFor(() => {
        expect(mockSetParams).toHaveBeenCalled();
      });
    });

    it('should read changes from URL params', async () => {
      mockSearchParams = new URLSearchParams({ query: 'initial query' });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.query), { wrapper: Wrapper })
      );

      expect(hook.result.current).toBe('initial query');

      // Simulate URL change
      mockSearchParams = new URLSearchParams({ query: 'updated query' });
      mockLocation.search = '?query=updated%20query';

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current).toBe('updated query');
      });
    });

    it('should handle bundle context - selected param synchronization', async () => {
      mockLocation.pathname = '/bundles/bundle_123';
      mockParams.id = 'bundle_123';

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper })
      );

      await waitFor(() => {
        expect(hook.result.current).toBe('bundle_123');
      });
    });

    it('should handle selected parameter in bundle when it matches bundle id', async () => {
      mockLocation.pathname = '/bundles/bundle_123';
      mockParams.id = 'bundle_123';
      mockSearchParams = new URLSearchParams({ selected: 'bundle_123' });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper })
      );

      expect(hook.result.current).toBe('bundle_123');
    });

    it('should handle selected parameter in bundle when it differs from bundle id', async () => {
      mockLocation.pathname = '/bundles/bundle_123';
      mockParams.id = 'bundle_123';
      mockSearchParams = new URLSearchParams({ selected: 'different_hit_id' });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper })
      );

      expect(hook.result.current).toBe('different_hit_id');
    });
  });

  describe('useParameterContextSelector', () => {
    it('should allow selecting specific values from context', async () => {
      mockSearchParams = new URLSearchParams({
        query: 'test query',
        sort: 'test.field asc'
      });

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              query: ctx.query,
              sort: ctx.sort
            })),
          { wrapper: Wrapper }
        )
      );

      expect(hook.result.current.query).toBe('test query');
      expect(hook.result.current.sort).toBe('test.field asc');
    });
  });

  describe('edge cases', () => {
    it('should handle offset of 0 in URL params', async () => {
      mockSearchParams = new URLSearchParams({ offset: '0' });

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.offset), { wrapper: Wrapper })
      );

      expect(hook.result.current).toBe(0);
    });

    it('should handle trackTotalHits with various values', async () => {
      mockSearchParams = new URLSearchParams({ track_total_hits: 'false' });

      let hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.trackTotalHits), { wrapper: Wrapper })
      );

      expect(hook.result.current).toBe(false);

      mockSearchParams = new URLSearchParams({ track_total_hits: 'true' });

      hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.trackTotalHits), { wrapper: Wrapper })
      );

      expect(hook.result.current).toBe(true);
    });

    it('should handle null and undefined values correctly', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              selected: ctx.selected,
              filters: ctx.filters,
              startDate: ctx.startDate,
              endDate: ctx.endDate
            })),
          { wrapper: Wrapper }
        )
      );

      // These should be null/undefined/empty when not set
      expect(hook.result.current.selected).toBeNull();
      expect(hook.result.current.filters).toEqual([]);
      expect(hook.result.current.startDate).toBeNull();
      expect(hook.result.current.endDate).toBeNull();
    });

    it('should fallback to default values when URL params are cleared', async () => {
      mockSearchParams = new URLSearchParams({
        query: 'custom query',
        sort: 'custom.sort asc',
        span: 'date.range.1.week'
      });
      mockLocation.search = mockSearchParams.toString();

      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              query: ctx.query,
              sort: ctx.sort,
              span: ctx.span
            })),
          { wrapper: Wrapper }
        )
      );

      expect(hook.result.current.query).toBe('custom query');

      // Simulate clearing URL params
      mockSearchParams = new URLSearchParams();
      mockLocation.search = '';

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current.query).toBe(DEFAULT_QUERY);
        expect(hook.result.current.sort).toBe('event.created desc');
        expect(hook.result.current.span).toBe('date.range.1.month');
      });
    });
  });

  describe('complex scenarios', () => {
    it('should handle multiple simultaneous parameter updates', async () => {
      const hook = await act(async () =>
        renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              query: ctx.query,
              sort: ctx.sort,
              span: ctx.span,
              filters: ctx.filters,
              setQuery: ctx.setQuery,
              setSort: ctx.setSort,
              setSpan: ctx.setSpan,
              addFilter: ctx.addFilter
            })),
          { wrapper: Wrapper }
        )
      );

      await act(async () => {
        hook.result.current.setQuery('multi query');
        hook.result.current.setSort('multi.sort desc');
        hook.result.current.setSpan('date.range.1.week');
        hook.result.current.addFilter('status:resolved');
      });

      await waitFor(() => {
        expect(hook.result.current.query).toBe('multi query');
        expect(hook.result.current.sort).toBe('multi.sort desc');
        expect(hook.result.current.span).toBe('date.range.1.week');
        expect(hook.result.current.filters).toEqual(['status:resolved']);
      });
    });

    it('should handle navigation between different contexts (hits to bundles)', async () => {
      mockLocation.pathname = '/hits';

      const hook = await act(async () =>
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper })
      );

      expect(hook.result.current).toBeNull();

      // Navigate to bundle
      mockLocation.pathname = '/bundles/bundle_456';
      mockParams.id = 'bundle_456';

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current).toBe('bundle_456');
      });
    });
  });
});
