import { identity, isEmpty, isEqual, isUndefined, omitBy, uniq } from 'lodash-es';
import type { Dispatch, FC, PropsWithChildren, SetStateAction } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useParams, useSearchParams } from 'react-router-dom';
import { createContext, useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY } from 'utils/constants';
import Throttler from 'utils/Throttler';

export type SearchIndex = 'hit' | 'observable' | 'case';

export interface ParameterContextType {
  selected?: string;
  query?: string;
  offset: number;
  trackTotalHits: boolean;
  sort?: string;
  span?: string;
  indexes?: SearchIndex[];
  filters?: string[];
  startDate?: string;
  endDate?: string;
  views?: string[];

  setSelected: (id: string) => void;
  setQuery: (id: string) => void;
  setOffset: (offset: string | number) => void;
  setSort: (sort: string) => void;
  setSpan: (span: string) => void;
  setCustomSpan: (startDate: string, endDate: string) => void;

  addFilter: (filter: string) => void;
  removeFilter: (filter: string) => void;
  setFilter: (index: number, filter: string) => void;
  resetFilters: () => void;

  addIndex: (index: SearchIndex) => void;
  removeIndex: (index: SearchIndex) => void;
  setIndex: (position: number, index: SearchIndex) => void;
  setIndexes: (indexes: SearchIndex[]) => void;
  resetIndexes: () => void;

  addView: (view: string) => void;
  removeView: (view: string) => void;
  setView: (index: number, view: string) => void;
  resetViews: () => void;
}

interface SearchValues {
  selected: string;
  query: string;
  sort: string;
  span: string;
  indexes: SearchIndex[];
  filters: string[];
  views: string[];
  startDate: string;
  endDate: string;
  offset: number;
  trackTotalHits: boolean;
}

export const ParameterContext = createContext<ParameterContextType>(null);

const DEFAULT_VALUES: Partial<SearchValues> = {
  query: DEFAULT_QUERY,
  sort: 'event.created desc',
  span: 'date.range.1.month',
  indexes: ['hit']
};

/** Scalar URL params that map 1:1 to a state key */
const PARAM_MAPPINGS: [string, keyof SearchValues][] = [
  ['query', 'query'],
  ['sort', 'sort'],
  ['span', 'span'],
  ['start_date', 'startDate'],
  ['end_date', 'endDate']
];

interface ArrayParamDescriptor {
  urlKey: string;
  stateKey: 'filters' | 'views' | 'indexes';
  default?: string[];
}

/** Multi-value URL params that map to array state keys */
const ARRAY_PARAMS: ArrayParamDescriptor[] = [
  { urlKey: 'filter', stateKey: 'filters' },
  { urlKey: 'view', stateKey: 'views' },
  { urlKey: 'index', stateKey: 'indexes', default: DEFAULT_VALUES.indexes }
];

const ARRAY_URL_KEYS = new Set(ARRAY_PARAMS.map(p => p.urlKey));

const WRITE_THROTTLER = new Throttler(100);

/**
 * Helper function to convert a number/string representation of a number into a valid offset.
 * @returns
 */
const parseOffset = (_offset: string | number) => {
  if (typeof _offset === 'number') return _offset;
  const candidate = parseInt(_offset);
  return isNaN(candidate) ? 0 : candidate;
};

/**
 * Helper function to determine the selected value based on URL params and route context.
 */
const getSelectedValue = (params: URLSearchParams, pathname: string, bundleId?: string) => {
  if (params.has('selected')) return params.get('selected');
  if (pathname.startsWith('/bundles') && bundleId) return bundleId;
  return null;
};

/**
 * Returns stable add / remove / setAt / setAll / clear handlers for a list field in
 * SearchValues. All returned functions are memoized; since _setValues (from useState)
 * and key are both stable for the lifetime of the component, the deps array is empty.
 */
const useListHandlers = <T,>(
  key: 'filters' | 'indexes' | 'views',
  _setValues: Dispatch<SetStateAction<SearchValues>>
) => {
  const add = useCallback(
    (item: T) => _setValues(c => ({ ...c, [key]: uniq([...(c[key] as T[]), item]) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const remove = useCallback(
    (item: T) =>
      _setValues(c => {
        const arr = c[key] as T[];
        const i = arr.indexOf(item);
        return i === -1 ? c : { ...c, [key]: arr.filter((_, idx) => idx !== i) };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const setAt = useCallback(
    (pos: number, item: T) =>
      _setValues(c => {
        const arr = c[key] as T[];
        if (pos < 0 || pos >= arr.length) return c;
        const next = [...arr] as T[];
        next[pos] = item;
        return { ...c, [key]: next };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const setAll = useCallback(
    (items: T[]) => _setValues(c => ({ ...c, [key]: uniq(items) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const reset = useCallback(
    (defaultValue: T[] = []) => _setValues(c => ({ ...c, [key]: defaultValue })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  return { add, remove, setAt, setAll, reset };
};

/**
 * Synchronizes SearchValues state with the URL search string, and vice-versa.
 */
const useUrlSync = (
  values: SearchValues,
  _setValues: Dispatch<SetStateAction<SearchValues>>,
  params: URLSearchParams,
  setParams: ReturnType<typeof useSearchParams>[1],
  pathname: string,
  search: string,
  routeId?: string
) => {
  const getUrlFromState = useCallback(() => {
    const changes: Record<string, unknown> = {};

    // Scalar params: write if changed from URL, remove if back to default
    PARAM_MAPPINGS.forEach(([urlKey, stateKey]) => {
      const stateValue = values[stateKey];
      const urlValue = params.get(urlKey);
      if (stateValue === urlValue) return;

      if (params.has(urlKey) && stateValue === DEFAULT_VALUES[stateKey]) {
        changes[urlKey] = null; // remove
      } else if (stateValue !== DEFAULT_VALUES[stateKey]) {
        changes[urlKey] = stateValue; // write
      }
    });

    // Array params: skip when state equals default and URL is already empty
    ARRAY_PARAMS.forEach(({ urlKey, stateKey, default: def }) => {
      const stateArr = values[stateKey] as string[];
      const urlArr = params.getAll(urlKey);
      if (isEqual(stateArr, urlArr)) return;

      const isDefault = def ? isEqual(stateArr, def) : stateArr.length === 0;
      if (!isDefault) {
        changes[urlKey] = stateArr.length === 0 ? null : stateArr;
      } else if (urlArr.length > 0) {
        changes[urlKey] = null; // state is default but URL isn't — remove
      }
    });

    // selected
    if (pathname.startsWith('/bundles') && (!params.has('selected') || values.selected === params.get('selected'))) {
      changes.selected = null;
    } else if (values.selected !== params.get('selected')) {
      changes.selected = values.selected;
    }

    // offset: remove when 0
    if (parseOffset(params.get('offset')) !== values.offset) {
      changes.offset = values.offset || null;
    }

    // Drop scalar entries that already match the URL
    return omitBy(changes, (val, key) => !ARRAY_URL_KEYS.has(key) && val == params.get(key));
  }, [values, params, pathname]);

  const getStateFromUrl = useCallback(() => {
    const changes: Partial<SearchValues> = {};

    // Scalar params: fall back to default when absent from URL
    PARAM_MAPPINGS.forEach(([urlKey, stateKey]) => {
      const urlValue = params.has(urlKey) ? params.get(urlKey) : (DEFAULT_VALUES[stateKey] ?? undefined);
      if (urlValue !== values[stateKey]) {
        (changes as any)[stateKey] = urlValue;
      }
    });

    // Array params: fall back to their declared default when absent from URL
    ARRAY_PARAMS.forEach(({ urlKey, stateKey, default: def }) => {
      const raw = params.getAll(urlKey);
      const resolved = (isEmpty(raw) && def ? def : uniq(raw)) as SearchValues[typeof stateKey];
      if (!isEqual(resolved, values[stateKey])) {
        (changes as any)[stateKey] = resolved;
      }
    });

    // selected
    const selectedValue = getSelectedValue(params, pathname, routeId);
    if (selectedValue !== values.selected) changes.selected = selectedValue;

    // offset
    const urlOffset = parseOffset(params.get('offset'));
    if (urlOffset !== values.offset) changes.offset = urlOffset;

    return omitBy(omitBy(changes, isUndefined), (val, key) => val == (values as any)[key]);
  }, [values, params, pathname, routeId]);

  // State → URL
  useEffect(() => {
    const changes = getUrlFromState();
    if (isEmpty(changes)) return;

    setParams(
      _params => {
        const newParams = new URLSearchParams(_params);
        Object.entries(changes).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            newParams.delete(key);
            (value as string[]).forEach(val => newParams.append(key, val));
          } else if (value === null || value === undefined) {
            newParams.delete(key);
          } else {
            newParams.set(key, String(value));
          }
        });
        return newParams;
      },
      { replace: !changes.query && !Object.keys(changes).includes('offset') }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values]);

  // URL → State
  useEffect(() => {
    const changes = getStateFromUrl();
    if (isEmpty(changes)) return;
    _setValues(c => ({ ...c, ...changes }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, pathname, routeId]);
};

/**
 * Context responsible for tracking updates to query operations in hit and view search.
 */
const ParameterProvider: FC<PropsWithChildren> = ({ children }) => {
  const location = useLocation();
  const routeParams = useParams();
  const [params, setParams] = useSearchParams();

  const pendingChanges = useRef<Partial<SearchValues>>({});

  const [values, _setValues] = useState<SearchValues>({
    selected: getSelectedValue(params, location.pathname, routeParams.id),
    query: params.get('query') ?? DEFAULT_VALUES.query,
    sort: params.get('sort') ?? DEFAULT_VALUES.sort,
    span: params.get('span') ?? DEFAULT_VALUES.span,
    indexes: params.has('index')
      ? uniq(params.getAll('index') as SearchIndex[]).filter(identity)
      : DEFAULT_VALUES.indexes,
    filters: params.getAll('filter'),
    views: params.getAll('view'),
    startDate: params.get('start_date'),
    endDate: params.get('end_date'),
    offset: parseOffset(params.get('offset')),
    trackTotalHits: (params.get('track_total_hits') ?? 'false') !== 'false'
  });

  // TODO: SELECTING A BUNDLE STILL CAUSES A FREAKOUT
  useUrlSync(values, _setValues, params, setParams, location.pathname, location.search, routeParams.id);

  const set = useCallback(
    <K extends keyof SearchValues>(key: K) =>
      (value: SearchValues[K]) => {
        if (value === values[key]) return;

        if (key === 'selected') {
          pendingChanges.current.selected = value as string | null;
        } else {
          (pendingChanges.current as any)[key] = value ?? DEFAULT_VALUES[key] ?? null;
        }

        if (key === 'span' && typeof value === 'string' && !value.endsWith('custom')) {
          pendingChanges.current.startDate = null;
          pendingChanges.current.endDate = null;
        }

        WRITE_THROTTLER.debounce(() => {
          _setValues(c => ({ ...c, ...pendingChanges.current }));
          pendingChanges.current = {};
        });
      },
    [values]
  );

  const setOffset = useCallback(
    (_offset: string | number) => _setValues(c => ({ ...c, offset: parseOffset(_offset) })),
    []
  );

  const setCustomSpan = useCallback(
    (startDate: string, endDate: string) => _setValues(c => ({ ...c, startDate, endDate })),
    []
  );

  const filters = useListHandlers<string>('filters', _setValues);
  const indexes = useListHandlers<SearchIndex>('indexes', _setValues);
  const views = useListHandlers<string>('views', _setValues);

  return (
    <ParameterContext.Provider
      value={{
        ...values,

        setOffset,
        setCustomSpan,

        setSelected: useMemo(() => set('selected'), [set]),
        setQuery: useMemo(() => set('query'), [set]),
        setSort: useMemo(() => set('sort'), [set]),
        setSpan: useMemo(() => set('span'), [set]),

        addFilter: filters.add,
        removeFilter: filters.remove,
        setFilter: filters.setAt,
        resetFilters: filters.reset,

        addIndex: indexes.add,
        removeIndex: indexes.remove,
        setIndex: indexes.setAt,
        setIndexes: indexes.setAll,
        resetIndexes: useCallback(() => indexes.reset(DEFAULT_VALUES.indexes), [indexes]),

        addView: views.add,
        removeView: views.remove,
        setView: views.setAt,
        resetViews: views.reset
      }}
    >
      {children}
    </ParameterContext.Provider>
  );
};

export const useParameterContextSelector = <Selected,>(
  selector: (value: ParameterContextType) => Selected
): Selected => {
  return useContextSelector<ParameterContextType, Selected>(ParameterContext, selector);
};

export default ParameterProvider;
