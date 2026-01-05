import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage, { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import dayjs from 'dayjs';
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
  /** @deprecated Use views[0] instead. Maintained for backward compatibility */
  viewId?: string;
  bundleId: string | null;
  fzfSearch: boolean;

  setDisplayType: (type: 'list' | 'grid') => void;
  setFzfSearch: Dispatch<SetStateAction<boolean>>;
  search: (query: string, appendResults?: boolean) => void;

  queryHistory: QueryEntry;
  setQueryHistory: ReturnType<typeof useMyLocalStorageItem>[1];
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

  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);
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
  const views = useContextSelector(ParameterContext, ctx => ctx.views);
  const addView = useContextSelector(ParameterContext, ctx => ctx.addView);

  const loadHits = useContextSelector(HitContext, ctx => ctx.loadHits);

  const [displayType, setDisplayType] = useState<'list' | 'grid'>(get(StorageKey.DISPLAY_TYPE) ?? 'list');
  const [searching, setSearching] = useState<boolean>(false);
  const [error, setError] = useState<string>(null);
  const [response, setResponse] = useState<HowlerSearchResponse<WithMetadata<Hit>>>(null);
  const [queryHistory, setQueryHistory] = useMyLocalStorageItem<Record<string, string>>(StorageKey.QUERY_HISTORY, {
    'howler.id: *': new Date().toISOString()
  });
  const [fzfSearch, setFzfSearch] = useState<boolean>(false);

  const viewId = useMemo(() => views[0] ?? null, [views]);

  const bundleId = useMemo(
    () => (location.pathname.startsWith('/bundles') ? routeParams.id : null),
    [location.pathname, routeParams.id]
  );

  const filters = useMemo(() => allFilters.filter(filter => !filter.endsWith('*')), [allFilters]);

  // On load check to filter out any queries older than one month
  useEffect(() => {
    const filterQueryTime = dayjs().subtract(1, 'month').toISOString();

    setQueryHistory(Object.fromEntries(Object.entries(queryHistory).filter(([_, value]) => value > filterQueryTime)));
  }, []);

  // Inject default view into URL when no views present
  useEffect(() => {
    if (views.length === 0 && defaultView) {
      addView(defaultView);
    }
  }, [views.length, defaultView]);

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

          setQueryHistory({
            ...queryHistory,
            [_query]: new Date().toISOString()
          });
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
            const viewObjects = await fetchViews(views);

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
      fetchViews,
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
