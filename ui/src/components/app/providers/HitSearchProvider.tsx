import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage, { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import i18n from 'i18n';
import { cloneDeep } from 'lodash-es';
import isNull from 'lodash-es/isNull';
import isUndefined from 'lodash-es/isUndefined';
import type { Hit } from 'models/entities/generated/Hit';
import type { WithMetadata } from 'models/WithMetadata';
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type FC,
  type PropsWithChildren,
  type SetStateAction
} from 'react';
import { useLocation, useParams, useSearchParams } from 'react-router-dom';
import { createContext, useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY, StorageKey } from 'utils/constants';
import Throttler from 'utils/Throttler';
import { convertCustomDateRangeToLucene, convertDateToLucene } from 'utils/utils';
import { HitContext } from './HitProvider';
import { ParameterContext } from './ParameterProvider';
import { ViewContext } from './ViewProvider';

export interface QueryEntry {
  [query: string]: string;
}

interface HitSearchProviderType {
  displayType: 'list' | 'grid';
  searching: boolean;
  error: string | null;
  response: HowlerSearchResponse<WithMetadata<Hit>> | null;
  views: string[];
  /** @deprecated Use views[0] instead. Maintained for backward compatibility */
  viewId?: string;
  bundleId: string | null;
  queryHistory: QueryEntry;
  fzfSearch: boolean;

  setDisplayType: (type: 'list' | 'grid') => void;
  setQueryHistory: Dispatch<SetStateAction<QueryEntry>>;
  setFzfSearch: Dispatch<SetStateAction<boolean>>;
  search: (query: string, appendResults?: boolean) => void;
}

export const HitSearchContext = createContext<HitSearchProviderType>(null);

const THROTTLER = new Throttler(500);

const HitSearchProvider: FC<PropsWithChildren> = ({ children }) => {
  const { get } = useMyLocalStorage();
  const routeParams = useParams();
  const location = useLocation();
  const { dispatchApi } = useMyApi();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];
  const [searchParams, setSearchParams] = useSearchParams();

  const getCurrentView = useContextSelector(ViewContext, ctx => ctx.getCurrentView);
  const defaultView = useContextSelector(ViewContext, ctx => ctx.defaultView);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);
  const offset = useContextSelector(ParameterContext, ctx => ctx.offset);
  const setOffset = useContextSelector(ParameterContext, ctx => ctx.setOffset);
  const trackTotalHits = useContextSelector(ParameterContext, ctx => ctx.trackTotalHits);
  const sort = useContextSelector(ParameterContext, ctx => ctx.sort);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const allFilters = useContextSelector(ParameterContext, ctx => ctx.filters);
  const startDate = useContextSelector(ParameterContext, ctx => ctx.startDate);
  const endDate = useContextSelector(ParameterContext, ctx => ctx.endDate);

  const loadHits = useContextSelector(HitContext, ctx => ctx.loadHits);

  const [displayType, setDisplayType] = useState<'list' | 'grid'>(get(StorageKey.DISPLAY_TYPE) ?? 'list');
  const [searching, setSearching] = useState<boolean>(false);
  const [error, setError] = useState<string>(null);
  const [response, setResponse] = useState<HowlerSearchResponse<WithMetadata<Hit>>>(null);
  const [queryHistory, setQueryHistory] = useState<QueryEntry>(
    get(StorageKey.QUERY_HISTORY) || { 'howler.id: *': new Date().toISOString() }
  );
  const [fzfSearch, setFzfSearch] = useState<boolean>(false);

  const views = useMemo(() => {
    const viewsArray: string[] = [];

    // Add route param view if on /views route
    if (location.pathname.startsWith('/views') && routeParams.id) {
      viewsArray.push(routeParams.id);
    }

    // Add all query param views
    const queryViews = searchParams.getAll('view');
    viewsArray.push(...queryViews);

    return viewsArray;
  }, [location.pathname, routeParams.id, searchParams.getAll('view').length]);

  console.log(views);

  const viewId = useMemo(() => views[0] ?? null, [views]);

  const bundleId = useMemo(
    () => (location.pathname.startsWith('/bundles') ? routeParams.id : null),
    [location.pathname, routeParams.id]
  );

  const filters = useMemo(() => allFilters.filter(filter => !filter.endsWith('*')), [allFilters]);

  // Inject default view into URL when no views present and not on /views route
  useEffect(() => {
    if (views.length === 0 && !location.pathname.startsWith('/views') && defaultView) {
      const newParams = new URLSearchParams(searchParams);
      newParams.set('view', defaultView);
      setSearchParams(newParams, { replace: true });
    }
  }, [views.length, location.pathname, defaultView, searchParams, setSearchParams]);

  const search = useCallback(
    async (_query?: string, appendResults?: boolean) => {
      THROTTLER.debounce(async () => {
        if (_query === 'woof!') {
          i18n.changeLanguage('woof');
          return;
        }

        if (isNull(sort) || isNull(span)) {
          return;
        }

        if (!isNull(_query) && !isUndefined(_query) && _query !== query) {
          setQuery(_query);
        }

        setSearching(true);
        setError(null);

        const _filters: string[] = cloneDeep(filters);

        if (span && !span.endsWith('custom')) {
          _filters.push(`event.created:${convertDateToLucene(span)}`);
        } else if (startDate && endDate) {
          _filters.push(`event.created:${convertCustomDateRangeToLucene(startDate, endDate)}`);
        }

        try {
          const bundle = location.pathname.startsWith('/bundles') && routeParams.id;

          let fullQuery = _query || DEFAULT_QUERY;
          if (bundle) {
            fullQuery = `(howler.bundles:${bundle}) AND (${fullQuery})`;
          } else if (views.length > 0) {
            // Fetch all view queries
            const viewObjects = await Promise.all(views.map(viewId => getCurrentView({ viewId })));

            // Filter out null/undefined views and extract queries
            const viewQueries = viewObjects.filter(view => view?.query).map(view => view.query);

            // Combine view queries with AND logic
            if (viewQueries.length > 0) {
              const combinedViewQuery = viewQueries.map(q => `(${q})`).join(' AND ');
              fullQuery = `(${combinedViewQuery}) AND (${fullQuery})`;
            }
          }

          const _response = await dispatchApi(
            api.search.hit.post({
              offset: appendResults && response ? response.rows : offset,
              rows: pageCount,
              query: fullQuery,
              sort,
              filters: _filters,
              track_total_hits: trackTotalHits,
              metadata: ['template', 'overview', 'analytic']
            }),
            { showError: false, throwError: true }
          );

          if (_response.total < offset) {
            setOffset(0);
          }

          loadHits(_response.items);

          if (!appendResults) {
            setResponse(_response);
          } else {
            setResponse(_existingResponse => ({
              ..._response,
              offset: _existingResponse.offset,
              rows: Math.min(_existingResponse.rows + _response.rows, _response.total),
              items: [..._existingResponse.items, ..._response.items]
            }));
          }
        } catch (e) {
          setError(e.message);
        } finally {
          setSearching(false);
        }
      });
    },
    // We skip reloading when the response changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      sort,
      span,
      query,
      startDate,
      endDate,
      filters,
      setQuery,
      location.pathname,
      routeParams.id,
      views,
      dispatchApi,
      offset,
      pageCount,
      trackTotalHits,
      loadHits,
      getCurrentView,
      setOffset
    ]
  );

  // We only run this when ancillary properties (i.e. filters, sorting) change
  useEffect(() => {
    if (span?.endsWith('custom') && (!startDate || !endDate)) {
      return;
    }

    if (views.length > 0 || bundleId || (query && query !== DEFAULT_QUERY) || offset > 0) {
      search(query);
    } else {
      setResponse(null);
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    offset,
    pageCount,
    sort,
    span,
    bundleId,
    location.pathname,
    startDate,
    endDate,
    filters.join(','),
    views.join(',')
  ]);

  return (
    <HitSearchContext.Provider
      value={{
        displayType,
        setDisplayType,
        search,
        searching,
        error,
        response,
        views,
        viewId,
        bundleId,
        setQueryHistory,
        queryHistory,
        fzfSearch,
        setFzfSearch
      }}
    >
      {children}
    </HitSearchContext.Provider>
  );
};

export const useHitSearchContextSelector = <Selected,>(
  selector: (value: HitSearchProviderType) => Selected
): Selected => {
  return useContextSelector<HitSearchProviderType, Selected>(HitSearchContext, selector);
};

export default HitSearchProvider;
