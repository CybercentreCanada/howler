import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage, { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import dayjs from 'dayjs';
import i18n from 'i18n';
import { cloneDeep, isNil } from 'lodash-es';
import isNull from 'lodash-es/isNull';
import isUndefined from 'lodash-es/isUndefined';
import type { Event } from 'models/entities/generated/Event';
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
import { useLocation } from 'react-router-dom';
import { createContext, useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY, StorageKey } from 'utils/constants';
import Throttler from 'utils/Throttler';
import { convertCustomDateRangeToLucene, convertDateToLucene } from 'utils/utils';
import { ParameterContext } from './ParameterProvider';
import { RecordContext } from './RecordProvider';
import { ViewContext } from './ViewProvider';

export interface QueryEntry {
  [query: string]: string;
}

export interface RecordSearchContextType {
  displayType: 'list' | 'grid';
  searching: boolean;
  error: string | null;
  response: HowlerSearchResponse<WithMetadata<Hit | Event>> | null;
  fzfSearch: boolean;

  setDisplayType: (type: 'list' | 'grid') => void;
  setFzfSearch: Dispatch<SetStateAction<boolean>>;
  search: (query: string, appendResults?: boolean) => void;
  getFilters: () => Promise<string[]>;

  queryHistory: QueryEntry;
  setQueryHistory: (value: Record<string, string>) => void;
}

export const RecordSearchContext = createContext<RecordSearchContextType>(null!);

const THROTTLER = new Throttler(500);

const RecordSearchProvider: FC<PropsWithChildren> = ({ children }) => {
  const { get } = useMyLocalStorage();
  const location = useLocation();
  const { dispatchApi } = useMyApi();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const getCurrentViews = useContextSelector(ViewContext, ctx => ctx.getCurrentViews);
  const defaultView = useContextSelector(ViewContext, ctx => ctx.defaultView);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);
  const offset = useContextSelector(ParameterContext, ctx => ctx.offset);
  const setOffset = useContextSelector(ParameterContext, ctx => ctx.setOffset);
  const trackTotalHits = useContextSelector(ParameterContext, ctx => ctx.trackTotalHits);
  const sort = useContextSelector(ParameterContext, ctx => ctx.sort);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const indexes = useContextSelector(ParameterContext, ctx => ctx.indexes);
  const allFilters = useContextSelector(ParameterContext, ctx => ctx.filters);
  const startDate = useContextSelector(ParameterContext, ctx => ctx.startDate);
  const endDate = useContextSelector(ParameterContext, ctx => ctx.endDate);
  const views = useContextSelector(ParameterContext, ctx => ctx.views);
  const addView = useContextSelector(ParameterContext, ctx => ctx.addView);

  const loadHits = useContextSelector(RecordContext, ctx => ctx.loadRecords);

  const [displayType, setDisplayType] = useState<'list' | 'grid'>(get(StorageKey.DISPLAY_TYPE) ?? 'list');
  const [searching, setSearching] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<HowlerSearchResponse<WithMetadata<Hit | Event>> | null>(null);
  const [queryHistory, setQueryHistory] = useMyLocalStorageItem<Record<string, string>>(StorageKey.QUERY_HISTORY, {
    'howler.id: *': new Date().toISOString()
  });
  const [fzfSearch, setFzfSearch] = useState<boolean>(false);

  const activeViews = views ?? [];

  const filters = useMemo(() => (allFilters ?? []).filter(filter => !filter.endsWith('*')), [allFilters]);

  // On load check to filter out any queries older than one month
  useEffect(() => {
    const filterQueryTime = dayjs().subtract(1, 'month').toISOString();

    setQueryHistory(Object.fromEntries(Object.entries(queryHistory).filter(([_, value]) => value > filterQueryTime)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Inject default view into URL when no views present
  useEffect(() => {
    if (activeViews.length === 0 && defaultView) {
      addView(defaultView);
    }
  }, [activeViews.length, defaultView, addView]);

  const getFilters = useCallback(async () => {
    const _filters: string[] = cloneDeep(filters);

    // Add span filter
    if (span && !span.endsWith('custom')) {
      _filters.push(`event.created:${convertDateToLucene(span)}`);
    } else if (startDate && endDate) {
      _filters.push(`event.created:${convertCustomDateRangeToLucene(startDate, endDate)}`);
    }

    // Fetch all view queries
    if (activeViews.length > 0) {
      const viewObjects = await getCurrentViews({ views: activeViews });

      // Filter out null/undefined views and extract queries
      viewObjects
        .filter(view => view?.query)
        .map(view => view.query)
        .forEach(viewQuery => _filters.push(viewQuery!));
    }

    return _filters;
  }, [activeViews, endDate, filters, getCurrentViews, span, startDate]);

  const search = useCallback(
    async (_query?: string, appendResults?: boolean) => {
      THROTTLER.debounce(async () => {
        if (_query === 'woof!') {
          void i18n.changeLanguage('woof');
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

        try {
          const _response = await dispatchApi(
            api.v2.search.post<WithMetadata<Hit | Event>>(indexes!, {
              offset: appendResults && !isNil(response?.rows) ? response.rows : offset,
              rows: pageCount,
              query: _query || DEFAULT_QUERY,
              sort,
              filters: await getFilters(),
              track_total_hits: trackTotalHits,
              metadata: ['template', 'overview', 'analytic']
            }),
            { showError: false, throwError: true }
          );

          if ((_response.total ?? 0) < offset) {
            setOffset(0);
          }

          loadHits(_response.items);

          if (!appendResults) {
            setResponse(_response);
          } else {
            setResponse(_existingResponse =>
              _existingResponse
                ? {
                    ..._response,
                    offset: _existingResponse.offset,
                    rows: Math.min(_existingResponse.rows + _response.rows, _response.total ?? Infinity),
                    items: [..._existingResponse.items, ..._response.items]
                  }
                : _response
            );
          }
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
        } finally {
          setSearching(false);
        }
      });
    },
    [
      sort,
      span,
      query,
      indexes,
      setQuery,
      setQueryHistory,
      queryHistory,
      response?.rows,
      offset,
      dispatchApi,
      pageCount,
      getFilters,
      trackTotalHits,
      loadHits,
      setOffset
    ]
  );

  // We only run this when ancillary properties (i.e. filters, sorting) change
  useEffect(() => {
    if (span?.endsWith('custom') && (!startDate || !endDate)) {
      return;
    }

    if (activeViews.length > 0 || (query && query !== DEFAULT_QUERY) || offset > 0 || filters.length > 0) {
      void search(query);
    } else {
      setResponse(null);
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, pageCount, sort, span, indexes, location.pathname, startDate, endDate, filters, query, activeViews]);

  return (
    <RecordSearchContext.Provider
      value={{
        displayType,
        setDisplayType,
        search,
        searching,
        getFilters,
        error,
        response,
        setQueryHistory,
        queryHistory,
        fzfSearch,
        setFzfSearch
      }}
    >
      {children}
    </RecordSearchContext.Provider>
  );
};

export default RecordSearchProvider;
