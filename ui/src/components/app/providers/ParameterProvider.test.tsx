import { act, renderHook, waitFor } from '@testing-library/react';
import { setupReactRouterMock } from 'tests/mocks';
import { useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY } from 'utils/constants';
import ParameterProvider, { ParameterContext } from './ParameterProvider';

// Mock dependencies
const { mockParams, mockLocation, mockSetParams, mockSearchParams } = setupReactRouterMock();

const Wrapper = ({ children }) => {
  return <ParameterProvider>{children}</ParameterProvider>;
};

beforeEach(() => {
  for (const key of [...mockSearchParams.keys()]) {
    mockSearchParams.delete(key);
  }
  mockSetParams.mockClear();
  mockLocation.pathname = '/hits';
  mockLocation.search = '';
  mockParams.id = undefined;
});

describe('ParameterContext', () => {
  it('should initialize with default values when no URL params are present', async () => {
    const hook = renderHook(
      () =>
        useContextSelector(ParameterContext, ctx => ({
          query: ctx.query,
          sort: ctx.sort,
          span: ctx.span,
          offset: ctx.offset,
          trackTotalHits: ctx.trackTotalHits
        })),
      { wrapper: Wrapper }
    );

    expect(hook.result.current.query).toBe(DEFAULT_QUERY);
    expect(hook.result.current.sort).toBe('event.created desc');
    expect(hook.result.current.span).toBe('date.range.1.month');
    expect(hook.result.current.offset).toBe(0);
    expect(hook.result.current.trackTotalHits).toBe(false);
  });

  it('should initialize with values from URL params', async () => {
    mockSearchParams.set('query', 'test query');
    mockSearchParams.set('sort', 'test.field asc');
    mockSearchParams.set('span', 'date.range.1.week');
    mockSearchParams.set('offset', '25');
    mockSearchParams.set('selected', 'test_id');
    mockSearchParams.set('filter', 'status:open');
    mockSearchParams.set('track_total_hits', 'true');

    const hook = renderHook(
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
    mockSearchParams.set('span', 'date.range.custom');
    mockSearchParams.set('start_date', '2025-01-01');
    mockSearchParams.set('end_date', '2025-12-31');

    const hook = renderHook(
      () =>
        useContextSelector(ParameterContext, ctx => ({
          span: ctx.span,
          startDate: ctx.startDate,
          endDate: ctx.endDate
        })),
      { wrapper: Wrapper }
    );

    expect(hook.result.current.span).toBe('date.range.custom');
    expect(hook.result.current.startDate).toBe('2025-01-01');
    expect(hook.result.current.endDate).toBe('2025-12-31');
  });

  describe('setQuery', () => {
    it('should update the query value', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            query: ctx.query,
            setQuery: ctx.setQuery
          })),
        { wrapper: Wrapper }
      );

      await act(async () => {
        hook.result.current.setQuery('new query');
      });

      await waitFor(() => {
        expect(hook.result.current.query).toBe('new query');
      });
    });

    it('should not update if the value is the same', async () => {
      mockSearchParams.set('query', 'existing query');

      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            query: ctx.query,
            setQuery: ctx.setQuery
          })),
        { wrapper: Wrapper }
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
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            sort: ctx.sort,
            setSort: ctx.setSort
          })),
        { wrapper: Wrapper }
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
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            span: ctx.span,
            setSpan: ctx.setSpan
          })),
        { wrapper: Wrapper }
      );

      await act(async () => {
        hook.result.current.setSpan('date.range.1.week');
      });

      await waitFor(() => {
        expect(hook.result.current.span).toBe('date.range.1.week');
      });
    });

    it('should clear startDate and endDate when span does not end with custom', async () => {
      mockSearchParams.set('span', 'date.range.custom');
      mockSearchParams.set('start_date', '2025-01-01');
      mockSearchParams.set('end_date', '2025-12-31');

      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            span: ctx.span,
            startDate: ctx.startDate,
            endDate: ctx.endDate,
            setSpan: ctx.setSpan
          })),
        { wrapper: Wrapper }
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
      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper });

      expect(hook.result.current).toEqual([]);
    });

    it('should initialize with single filter from URL', async () => {
      mockSearchParams.set('filter', 'status:open');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['status:open']);
    });

    it('should initialize with multiple filters from URL', async () => {
      mockSearchParams.append('filter', 'howler.escalation:hit');
      mockSearchParams.append('filter', 'howler.assignment:someuser');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['howler.escalation:hit', 'howler.assignment:someuser']);
    });

    it('should preserve filter order from URL', async () => {
      mockSearchParams.append('filter', 'c');
      mockSearchParams.append('filter', 'a');
      mockSearchParams.append('filter', 'b');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['c', 'a', 'b']);
    });

    it('should deduplicate multiple empty filter params to single empty string', async () => {
      mockSearchParams.append('filter', '');
      mockSearchParams.append('filter', '');
      mockSearchParams.append('filter', '');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.filters), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['']);
    });

    describe('addFilter', () => {
      it('should add a filter to empty array', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              addFilter: ctx.addFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addFilter('status:open');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['status:open']);
        });
      });

      it('should append filter to existing filters', async () => {
        mockSearchParams.set('filter', 'existing:filter');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              addFilter: ctx.addFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addFilter('new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing:filter', 'new:filter']);
        });
      });

      it('should not add duplicate filters', async () => {
        mockSearchParams.set('filter', 'status:open');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              addFilter: ctx.addFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addFilter('status:open');
        });

        await waitFor(() => {
          // Should still have only one filter, not two
          expect(hook.result.current.filters).toEqual(['status:open']);
        });
      });
    });

    describe('removeFilter', () => {
      it('should remove first matching filter', async () => {
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');
        mockSearchParams.append('filter', 'filter3');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              removeFilter: ctx.removeFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeFilter('filter2');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['filter1', 'filter3']);
        });
      });

      it('should do nothing when removing nonexistent filter', async () => {
        mockSearchParams.set('filter', 'existing');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              removeFilter: ctx.removeFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeFilter('nonexistent');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing']);
        });
      });

      it('should handle removing from empty array', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              removeFilter: ctx.removeFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeFilter('anything');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });
    });

    describe('resetFilters', () => {
      it('should clear all filters', async () => {
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              resetFilters: ctx.resetFilters
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetFilters();
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });

      it('should be no-op when already empty', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              resetFilters: ctx.resetFilters
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetFilters();
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });
    });

    describe('setFilter', () => {
      it('should update filter at specified index', async () => {
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');
        mockSearchParams.append('filter', 'filter3');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              setFilter: ctx.setFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setFilter(1, 'updated:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['filter1', 'updated:filter', 'filter3']);
        });
      });

      it('should update filter at index 0', async () => {
        mockSearchParams.append('filter', 'old:filter');
        mockSearchParams.append('filter', 'filter2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              setFilter: ctx.setFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setFilter(0, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['new:filter', 'filter2']);
        });
      });

      it('should update filter at last index', async () => {
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'old:last');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              setFilter: ctx.setFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setFilter(1, 'new:last');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['filter1', 'new:last']);
        });
      });

      it('should do nothing when index is out of bounds', async () => {
        mockSearchParams.set('filter', 'existing');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              setFilter: ctx.setFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setFilter(5, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing']);
        });
      });

      it('should do nothing when index is negative', async () => {
        mockSearchParams.set('filter', 'existing');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              setFilter: ctx.setFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setFilter(-1, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual(['existing']);
        });
      });

      it('should do nothing when array is empty', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              filters: ctx.filters,
              setFilter: ctx.setFilter
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setFilter(0, 'new:filter');
        });

        await waitFor(() => {
          expect(hook.result.current.filters).toEqual([]);
        });
      });

      it('should sync updated filter to URL', async () => {
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              setFilter: ctx.setFilter
            })),
          { wrapper: Wrapper }
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
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addFilter: ctx.addFilter
            })),
          { wrapper: Wrapper }
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
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addFilter: ctx.addFilter
            })),
          { wrapper: Wrapper }
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
        mockSearchParams.append('filter', 'filter1');
        mockSearchParams.append('filter', 'filter2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              resetFilters: ctx.resetFilters
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetFilters();
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('filter')).toEqual([]);
        });
      });

      it('should preserve filter order when syncing to URL', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addFilter: ctx.addFilter
            })),
          { wrapper: Wrapper }
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
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            selected: ctx.selected,
            setSelected: ctx.setSelected
          })),
        { wrapper: Wrapper }
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

      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            selected: ctx.selected,
            setSelected: ctx.setSelected
          })),
        { wrapper: Wrapper }
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
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            offset: ctx.offset,
            setOffset: ctx.setOffset
          })),
        { wrapper: Wrapper }
      );

      await act(async () => {
        hook.result.current.setOffset(50);
      });

      await waitFor(() => {
        expect(hook.result.current.offset).toBe(50);
      });
    });

    it('should update the offset with a string', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            offset: ctx.offset,
            setOffset: ctx.setOffset
          })),
        { wrapper: Wrapper }
      );

      await act(async () => {
        hook.result.current.setOffset('100');
      });

      await waitFor(() => {
        expect(hook.result.current.offset).toBe(100);
      });
    });

    it('should handle invalid string offset by setting to 0', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            offset: ctx.offset,
            setOffset: ctx.setOffset
          })),
        { wrapper: Wrapper }
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
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            startDate: ctx.startDate,
            endDate: ctx.endDate,
            setCustomSpan: ctx.setCustomSpan
          })),
        { wrapper: Wrapper }
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
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            setQuery: ctx.setQuery,
            setSort: ctx.setSort
          })),
        { wrapper: Wrapper }
      );

      await act(async () => {
        hook.result.current.setQuery('new query');
      });

      await waitFor(() => {
        expect(mockSetParams).toHaveBeenCalled();
      });
    });

    it('should read changes from URL params', async () => {
      mockSearchParams.set('query', 'initial query');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.query), { wrapper: Wrapper });

      expect(hook.result.current).toBe('initial query');

      // Simulate URL change
      mockSearchParams.set('query', 'updated query');
      mockLocation.search = '?query=updated%20query';

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current).toBe('updated query');
      });
    });

    it('should handle bundle context - selected param synchronization', async () => {
      mockLocation.pathname = '/bundles/bundle_123';
      mockParams.id = 'bundle_123';

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper });

      await waitFor(() => {
        expect(hook.result.current).toBe('bundle_123');
      });
    });

    it('should handle selected parameter in bundle when it matches bundle id', async () => {
      mockLocation.pathname = '/bundles/bundle_123';
      mockParams.id = 'bundle_123';
      mockSearchParams.set('selected', 'bundle_123');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper });

      expect(hook.result.current).toBe('bundle_123');
    });

    it('should handle selected parameter in bundle when it differs from bundle id', async () => {
      mockLocation.pathname = '/bundles/bundle_123';
      mockParams.id = 'bundle_123';
      mockSearchParams.set('selected', 'different_hit_id');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper });

      expect(hook.result.current).toBe('different_hit_id');
    });
  });

  describe('useParameterContextSelector', () => {
    it('should allow selecting specific values from context', async () => {
      mockSearchParams.set('query', 'test query');
      mockSearchParams.set('sort', 'test.field asc');

      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            query: ctx.query,
            sort: ctx.sort
          })),
        { wrapper: Wrapper }
      );

      expect(hook.result.current.query).toBe('test query');
      expect(hook.result.current.sort).toBe('test.field asc');
    });
  });

  describe('edge cases', () => {
    it('should handle offset of 0 in URL params', async () => {
      mockSearchParams.set('offset', '0');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.offset), { wrapper: Wrapper });

      expect(hook.result.current).toBe(0);
    });

    it('should handle trackTotalHits with various values', async () => {
      mockSearchParams.set('track_total_hits', 'false');

      let hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.trackTotalHits), {
        wrapper: Wrapper
      });

      expect(hook.result.current).toBe(false);

      mockSearchParams.set('track_total_hits', 'true');

      hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.trackTotalHits), { wrapper: Wrapper });

      expect(hook.result.current).toBe(true);
    });

    it('should handle null and undefined values correctly', async () => {
      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            selected: ctx.selected,
            filters: ctx.filters,
            startDate: ctx.startDate,
            endDate: ctx.endDate
          })),
        { wrapper: Wrapper }
      );

      // These should be null/undefined/empty when not set
      expect(hook.result.current.selected).toBeNull();
      expect(hook.result.current.filters).toEqual([]);
      expect(hook.result.current.startDate).toBeNull();
      expect(hook.result.current.endDate).toBeNull();
    });

    it('should fallback to default values when URL params are cleared', async () => {
      mockSearchParams.set('query', 'custom query');
      mockSearchParams.set('sort', 'custom.sort asc');
      mockSearchParams.set('span', 'date.range.1.week');
      mockLocation.search = mockSearchParams.toString();

      const hook = renderHook(
        () =>
          useContextSelector(ParameterContext, ctx => ({
            query: ctx.query,
            sort: ctx.sort,
            span: ctx.span
          })),
        { wrapper: Wrapper }
      );

      expect(hook.result.current.query).toBe('custom query');

      // Simulate clearing URL params
      for (const key of [...mockSearchParams.keys()]) {
        mockSearchParams.delete(key);
      }
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
      const hook = renderHook(
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
      );

      await act(async () => {
        hook.result.current.setQuery('multi query');
        hook.result.current.setSort('multi.sort desc');
        hook.result.current.setSpan('date.range.1.week');
        hook.result.current.addFilter('status:resolved');
      });

      hook.rerender();

      await waitFor(() => {
        expect(hook.result.current.query).toBe('multi query');
        expect(hook.result.current.sort).toBe('multi.sort desc');
        expect(hook.result.current.span).toBe('date.range.1.week');
        expect(hook.result.current.filters).toEqual(['status:resolved']);
      });
    });

    it('should handle navigation between different contexts (hits to bundles)', async () => {
      mockLocation.pathname = '/hits';

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.selected), { wrapper: Wrapper });

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

  describe('indexes (multi-index support)', () => {
    it('should initialize with default ["hit"] when no index params are present', async () => {
      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.indexes), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['hit']);
    });

    it('should initialize with single index from URL', async () => {
      mockSearchParams.set('index', 'observable');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.indexes), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['observable']);
    });

    it('should initialize with multiple indexes from URL', async () => {
      mockSearchParams.append('index', 'hit');
      mockSearchParams.append('index', 'observable');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.indexes), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['hit', 'observable']);
    });

    it('should deduplicate repeated index values from URL', async () => {
      mockSearchParams.append('index', 'hit');
      mockSearchParams.append('index', 'hit');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.indexes), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['hit']);
    });

    describe('addIndex', () => {
      it('should add an index to the default array', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              addIndex: ctx.addIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addIndex('observable');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit', 'observable']);
        });
      });

      it('should not add a duplicate index', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              addIndex: ctx.addIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addIndex('hit');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit']);
        });
      });
    });

    describe('removeIndex', () => {
      it('should remove an index from the list', async () => {
        mockSearchParams.append('index', 'hit');
        mockSearchParams.append('index', 'observable');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              removeIndex: ctx.removeIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeIndex('hit');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['observable']);
        });
      });

      it('should do nothing when removing a nonexistent index', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              removeIndex: ctx.removeIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeIndex('observable');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit']);
        });
      });

      it('should handle removing from empty array', async () => {
        mockSearchParams.append('index', 'hit');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              removeIndex: ctx.removeIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeIndex('hit');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual([]);
        });
      });
    });

    describe('setIndex', () => {
      it('should update the index at the specified position', async () => {
        mockSearchParams.append('index', 'hit');
        mockSearchParams.append('index', 'observable');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              setIndex: ctx.setIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setIndex(0, 'observable');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['observable', 'observable']);
        });
      });

      it('should do nothing when index is out of bounds', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              setIndex: ctx.setIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setIndex(5, 'observable');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit']);
        });
      });

      it('should do nothing when position is negative', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              setIndex: ctx.setIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setIndex(-1, 'observable');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit']);
        });
      });
    });

    describe('setIndexes', () => {
      it('should replace all indexes with the provided list', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              setIndexes: ctx.setIndexes
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setIndexes(['observable']);
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['observable']);
        });
      });

      it('should deduplicate values when setting all indexes', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              setIndexes: ctx.setIndexes
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setIndexes(['hit', 'hit', 'observable']);
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit', 'observable']);
        });
      });

      it('should set to empty array', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              setIndexes: ctx.setIndexes
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setIndexes([]);
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual([]);
        });
      });
    });

    describe('resetIndexes', () => {
      it('should reset indexes to default ["hit"]', async () => {
        mockSearchParams.append('index', 'hit');
        mockSearchParams.append('index', 'observable');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              resetIndexes: ctx.resetIndexes
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetIndexes();
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit']);
        });
      });

      it('should reset to default even when called on empty array', async () => {
        mockSearchParams.append('index', 'hit');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              indexes: ctx.indexes,
              removeIndex: ctx.removeIndex,
              resetIndexes: ctx.resetIndexes
            })),
          { wrapper: Wrapper }
        );

        // First empty it
        await act(async () => {
          hook.result.current.removeIndex('hit');
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual([]);
        });

        // Resetting always returns to default ['hit']
        await act(async () => {
          hook.result.current.resetIndexes();
        });

        await waitFor(() => {
          expect(hook.result.current.indexes).toEqual(['hit']);
        });
      });
    });

    describe('URL synchronization', () => {
      it('should not write the default ["hit"] index to the URL', async () => {
        renderHook(() => useContextSelector(ParameterContext, ctx => ctx.indexes), { wrapper: Wrapper });

        // Allow any effects to flush
        await waitFor(() => {
          // If setParams was called, the URL must not contain ?index=hit
          if (mockSetParams.mock.calls.length > 0) {
            const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
            const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
            expect(urlParams.getAll('index')).toEqual([]);
          } else {
            // setParams not called at all is also fine
            expect(true).toBe(true);
          }
        });
      });

      it('should write a non-default index to the URL', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addIndex: ctx.addIndex,
              resetIndexes: ctx.resetIndexes
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetIndexes();
          hook.result.current.addIndex('observable');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('index')).toEqual(['hit', 'observable']);
        });
      });

      it('should sync multiple indexes to URL as multiple index params', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addIndex: ctx.addIndex
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addIndex('observable');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('index')).toEqual(['hit', 'observable']);
        });
      });

      it('should remove all index params from URL when state resets to default', async () => {
        mockSearchParams.append('index', 'hit');
        mockSearchParams.append('index', 'observable');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              resetIndexes: ctx.resetIndexes
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetIndexes();
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('index')).toEqual([]);
        });
      });

      it('should remove index param from URL when state returns to default', async () => {
        mockSearchParams.set('index', 'observable');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              setIndexes: ctx.setIndexes
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setIndexes(['hit']);
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('index')).toEqual([]);
        });
      });
    });
  });

  describe('views (multi-view support)', () => {
    it('should initialize with empty array when no view params present', async () => {
      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.views), { wrapper: Wrapper });

      expect(hook.result.current).toEqual([]);
    });

    it('should initialize with single view from URL', async () => {
      mockSearchParams.set('view', 'view_1');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.views), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['view_1']);
    });

    it('should initialize with multiple views from URL', async () => {
      mockSearchParams.append('view', 'view_1');
      mockSearchParams.append('view', 'view_2');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.views), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['view_1', 'view_2']);
    });

    it('should preserve view order from URL', async () => {
      mockSearchParams.append('view', 'view_c');
      mockSearchParams.append('view', 'view_a');
      mockSearchParams.append('view', 'view_b');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.views), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['view_c', 'view_a', 'view_b']);
    });

    it('should deduplicate multiple empty view params to single empty string', async () => {
      mockSearchParams.append('view', '');
      mockSearchParams.append('view', '');
      mockSearchParams.append('view', '');

      const hook = renderHook(() => useContextSelector(ParameterContext, ctx => ctx.views), { wrapper: Wrapper });

      expect(hook.result.current).toEqual(['']);
    });

    describe('addView', () => {
      it('should add a view to empty array', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              addView: ctx.addView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addView('view_1');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['view_1']);
        });
      });

      it('should append view to existing views', async () => {
        mockSearchParams.set('view', 'existing_view');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              addView: ctx.addView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addView('new_view');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['existing_view', 'new_view']);
        });
      });

      it('should not add duplicate views', async () => {
        mockSearchParams.set('view', 'view_1');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              addView: ctx.addView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addView('view_1');
        });

        await waitFor(() => {
          // Should still have only one view, not two
          expect(hook.result.current.views).toEqual(['view_1']);
        });
      });
    });

    describe('removeView', () => {
      it('should remove first matching view', async () => {
        mockSearchParams.append('view', 'view_1');
        mockSearchParams.append('view', 'view_2');
        mockSearchParams.append('view', 'view_3');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              removeView: ctx.removeView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeView('view_2');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['view_1', 'view_3']);
        });
      });

      it('should remove only first occurrence of duplicate views', async () => {
        mockSearchParams.append('view', 'dup');
        mockSearchParams.append('view', 'dup');
        mockSearchParams.append('view', 'other');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              removeView: ctx.removeView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeView('dup');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['other']);
        });
      });

      it('should do nothing when removing nonexistent view', async () => {
        mockSearchParams.set('view', 'existing');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              removeView: ctx.removeView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeView('nonexistent');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['existing']);
        });
      });

      it('should handle removing from empty array', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              removeView: ctx.removeView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.removeView('anything');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual([]);
        });
      });
    });

    describe('resetViews', () => {
      it('should clear all views', async () => {
        mockSearchParams.append('view', 'view_1');
        mockSearchParams.append('view', 'view_2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              resetViews: ctx.resetViews
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetViews();
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual([]);
        });
      });

      it('should be no-op when already empty', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              resetViews: ctx.resetViews
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetViews();
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual([]);
        });
      });
    });

    describe('setView', () => {
      it('should update view at specified index', async () => {
        mockSearchParams.append('view', 'view_1');
        mockSearchParams.append('view', 'view_2');
        mockSearchParams.append('view', 'view_3');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              setView: ctx.setView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setView(1, 'updated_view');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['view_1', 'updated_view', 'view_3']);
        });
      });

      it('should update view at index 0', async () => {
        mockSearchParams.append('view', 'old_view');
        mockSearchParams.append('view', 'view_2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              setView: ctx.setView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setView(0, 'new_view');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['new_view', 'view_2']);
        });
      });

      it('should update view at last index', async () => {
        mockSearchParams.append('view', 'view_1');
        mockSearchParams.append('view', 'old_last');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              setView: ctx.setView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setView(1, 'new_last');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['view_1', 'new_last']);
        });
      });

      it('should do nothing when index is out of bounds', async () => {
        mockSearchParams.set('view', 'existing');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              setView: ctx.setView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setView(5, 'new_view');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['existing']);
        });
      });

      it('should do nothing when index is negative', async () => {
        mockSearchParams.set('view', 'existing');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              setView: ctx.setView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setView(-1, 'new_view');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual(['existing']);
        });
      });

      it('should do nothing when array is empty', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              views: ctx.views,
              setView: ctx.setView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setView(0, 'new_view');
        });

        await waitFor(() => {
          expect(hook.result.current.views).toEqual([]);
        });
      });

      it('should sync updated view to URL', async () => {
        mockSearchParams.append('view', 'view_1');
        mockSearchParams.append('view', 'view_2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              setView: ctx.setView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.setView(0, 'updated_view');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('view')).toEqual(['updated_view', 'view_2']);
        });
      });
    });

    describe('URL synchronization', () => {
      it('should sync single view to URL as view param', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addView: ctx.addView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addView('test_view');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('view')).toEqual(['test_view']);
        });
      });

      it('should sync multiple views to URL as multiple view params', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addView: ctx.addView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addView('view_1');
        });

        await act(async () => {
          hook.result.current.addView('view_2');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('view')).toEqual(['view_1', 'view_2']);
        });
      });

      it('should remove all view params when views is empty', async () => {
        mockSearchParams.append('view', 'view_1');
        mockSearchParams.append('view', 'view_2');

        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              resetViews: ctx.resetViews
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.resetViews();
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('view')).toEqual([]);
        });
      });

      it('should preserve view order when syncing to URL', async () => {
        const hook = renderHook(
          () =>
            useContextSelector(ParameterContext, ctx => ({
              addView: ctx.addView
            })),
          { wrapper: Wrapper }
        );

        await act(async () => {
          hook.result.current.addView('z');
          hook.result.current.addView('a');
          hook.result.current.addView('m');
        });

        await waitFor(() => {
          expect(mockSetParams).toHaveBeenCalled();
          const call = mockSetParams.mock.calls[mockSetParams.mock.calls.length - 1];
          const urlParams = typeof call[0] === 'function' ? call[0](mockSearchParams) : call[0];
          expect(urlParams.getAll('view')).toEqual(['z', 'a', 'm']);
        });
      });
    });
  });
});
