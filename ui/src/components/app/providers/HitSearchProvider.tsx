import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage, { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import i18n from 'i18n';
import isNull from 'lodash-es/isNull';
import isUndefined from 'lodash-es/isUndefined';
import type { Hit } from 'models/entities/generated/Hit';
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
import { isMobile } from 'react-device-detect';
import { useLocation, useParams } from 'react-router-dom';
import { createContext, useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import Throttler from 'utils/Throttler';
import { convertCustomDateRangeToLucene, convertDateToLucene } from 'utils/utils';
import { HitContext } from './HitProvider';
import { ParameterContext } from './ParameterProvider';
import { ViewContext } from './ViewProvider';

export interface QueryEntry {
  [query: string]: string;
}

interface HitSearchProviderType {
  layout: HitLayout;
  displayType: 'list' | 'grid';
  searching: boolean;
  error: string | null;
  response: HowlerSearchResponse<Hit> | null;
  viewId: string | null;
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

  const viewsReady = useContextSelector(ViewContext, ctx => ctx.ready);
  const views = useContextSelector(ViewContext, ctx => ctx.views);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);
  const offset = useContextSelector(ParameterContext, ctx => ctx.offset);
  const setOffset = useContextSelector(ParameterContext, ctx => ctx.setOffset);
  const trackTotalHits = useContextSelector(ParameterContext, ctx => ctx.trackTotalHits);
  const sort = useContextSelector(ParameterContext, ctx => ctx.sort);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const filter = useContextSelector(ParameterContext, ctx => ctx.filter);
  const startDate = useContextSelector(ParameterContext, ctx => ctx.startDate);
  const endDate = useContextSelector(ParameterContext, ctx => ctx.endDate);

  const loadHits = useContextSelector(HitContext, ctx => ctx.loadHits);

  const [displayType, setDisplayType] = useState<'list' | 'grid'>('list');
  const [searching, setSearching] = useState<boolean>(false);
  const [error, setError] = useState<string>(null);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit>>();
  const [queryHistory, setQueryHistory] = useState<QueryEntry>(
    JSON.parse(get(StorageKey.QUERY_HISTORY)) || { 'howler.id: *': new Date().toISOString() }
  );
  const [fzfSearch, setFzfSearch] = useState<boolean>(false);

  const viewId = useMemo(
    () => (location.pathname.startsWith('/views') ? routeParams.id : null),
    [location.pathname, routeParams.id]
  );

  const bundleId = useMemo(
    () => (location.pathname.startsWith('/bundles') ? routeParams.id : null),
    [location.pathname, routeParams.id]
  );

  const layout: HitLayout = useMemo(
    () => (isMobile ? HitLayout.COMFY : (get(StorageKey.HIT_LAYOUT) ?? HitLayout.NORMAL)),
    [get]
  );

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

        const filters: string[] = [];

        if (span && !span.endsWith('custom')) {
          filters.push(`event.created:${convertDateToLucene(span)}`);
        } else if (startDate && endDate) {
          filters.push(`event.created:${convertCustomDateRangeToLucene(startDate, endDate)}`);
        }

        if (filter) {
          filters.push(filter);
        }

        try {
          const bundle = location.pathname.startsWith('/bundles') && routeParams.id;

          let fullQuery = _query || 'howler.id:*';
          if (bundle) {
            fullQuery = `(howler.bundles:${bundle}) AND (${fullQuery})`;
          } else if (viewId) {
            fullQuery = `(${views.find(_view => _view.view_id === viewId)?.query || 'howler.id:*'}) AND (${fullQuery})`;
          }

          const _response = await dispatchApi(
            api.search.hit.post({
              offset: appendResults ? response.rows : offset,
              rows: pageCount,
              query: fullQuery,
              sort,
              filters,
              track_total_hits: trackTotalHits
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
      filter,
      setQuery,
      location.pathname,
      routeParams.id,
      viewId,
      dispatchApi,
      offset,
      pageCount,
      trackTotalHits,
      loadHits,
      views,
      setOffset
    ]
  );

  // We only run this when ancillary properties (i.e. filters, sorting) change
  useEffect(() => {
    // We're being asked to present a view, but we don't currently have the views loaded
    if (viewId && !viewsReady) {
      return;
    }

    if (span.endsWith('custom') && (!startDate || !endDate)) {
      return;
    }

    if (viewId || bundleId || (query && query !== 'howler.id:*') || offset > 0) {
      search(query);
    } else {
      setResponse(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, offset, pageCount, sort, span, bundleId, location.pathname, viewsReady, startDate, endDate]);

  return (
    <HitSearchContext.Provider
      value={{
        layout,
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

export default HitSearchProvider;
