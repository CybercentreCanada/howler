import type { SearchIndex } from 'api/v2/search';
import { has, identity, isEmpty, isEqual, isNil, isUndefined, omitBy, uniq } from 'lodash-es';
import type { Dispatch, FC, PropsWithChildren, SetStateAction } from 'react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useParams, useSearchParams } from 'react-router';
import { createContext, useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY } from 'utils/constants';
import { notNil } from 'utils/utils';
import { missingContext } from './contextUtils';

export interface ParameterContextType {
  selected?: string | null;
  query?: string;
  offset: number;
  trackTotalHits: boolean;
  sort?: string;
  span?: string;
  indexes?: SearchIndex[];
  filters?: string[];
  disabledFilterIndexes: number[];
  startDate?: string | null;
  endDate?: string | null;
  views?: string[];
  disabledViewIndexes: number[];

  setSelected: (id: string | null) => void;
  setQuery: (id: string) => void;
  setOffset: (offset: string | number) => void;
  setSort: (sort: string) => void;
  setSpan: (span: string) => void;
  setCustomSpan: (startDate: string, endDate: string) => void;

  addFilter: (filter: string) => void;
  removeFilter: (filter: string) => void;
  enableFilter: (index: number) => void;
  disableFilter: (index: number) => void;
  setFilter: (index: number, filter: string) => void;
  resetFilters: () => void;

  addIndex: (index: SearchIndex) => void;
  removeIndex: (index: SearchIndex) => void;
  setIndex: (position: number, index: SearchIndex) => void;
  setIndexes: (indexes: SearchIndex[]) => void;
  resetIndexes: () => void;

  addView: (view: string) => void;
  removeView: (view: string) => void;
  enableView: (index: number) => void;
  disableView: (index: number) => void;
  setView: (index: number, view: string) => void;
  resetViews: () => void;
}

interface SearchValues {
  selected: string | null;
  query: string;
  sort: string;
  span: string;
  indexes: SearchIndex[];
  filters: string[];
  disabledFilterIndexes: number[];
  views: string[];
  disabledViewIndexes: number[];
  startDate: string | null;
  endDate: string | null;
  offset: number;
  trackTotalHits: boolean;
}

const DEFAULT_VALUES: Pick<SearchValues, 'query' | 'sort' | 'span' | 'indexes'> = {
  query: DEFAULT_QUERY,
  sort: 'event.created desc',
  span: 'date.range.1.month',
  indexes: ['hit']
};

const DEFAULT_PARAMETER_CONTEXT: ParameterContextType = {
  ...DEFAULT_VALUES,
  selected: null,
  offset: 0,
  trackTotalHits: false,
  filters: [],
  disabledFilterIndexes: [],
  startDate: null,
  endDate: null,
  views: [],
  disabledViewIndexes: [],
  setSelected: () => missingContext('ParameterContext'),
  setQuery: () => missingContext('ParameterContext'),
  setOffset: () => missingContext('ParameterContext'),
  setSort: () => missingContext('ParameterContext'),
  setSpan: () => missingContext('ParameterContext'),
  setCustomSpan: () => missingContext('ParameterContext'),
  addFilter: () => missingContext('ParameterContext'),
  removeFilter: () => missingContext('ParameterContext'),
  setFilter: () => missingContext('ParameterContext'),
  enableFilter: () => missingContext('ParameterContext'),
  disableFilter: () => missingContext('ParameterContext'),
  resetFilters: () => missingContext('ParameterContext'),
  addIndex: () => missingContext('ParameterContext'),
  removeIndex: () => missingContext('ParameterContext'),
  setIndex: () => missingContext('ParameterContext'),
  setIndexes: () => missingContext('ParameterContext'),
  resetIndexes: () => missingContext('ParameterContext'),
  addView: () => missingContext('ParameterContext'),
  removeView: () => missingContext('ParameterContext'),
  enableView: () => missingContext('ParameterContext'),
  disableView: () => missingContext('ParameterContext'),
  setView: () => missingContext('ParameterContext'),
  resetViews: () => missingContext('ParameterContext')
};

export const ParameterContext = createContext<ParameterContextType>(DEFAULT_PARAMETER_CONTEXT);

/** Scalar URL params that map 1:1 to a state key */
const PARAM_MAPPINGS: [string, keyof SearchValues][] = [
  ['query', 'query'],
  ['sort', 'sort'],
  ['span', 'span'],
  ['start_date', 'startDate'],
  ['end_date', 'endDate']
];

type ListKey = 'filters' | 'views' | 'indexes';
type DisabledListKey = 'disabledFilterIndexes' | 'disabledViewIndexes';

interface ArrayParamDescriptor {
  urlKey: string;
  stateKey: ListKey;
  disabled?: { urlKey: string; stateKey: DisabledListKey };
}

/** Multi-value URL params that map to array state keys */
const ARRAY_PARAMS: ArrayParamDescriptor[] = [
  { urlKey: 'filter', stateKey: 'filters', disabled: { urlKey: 'disabled_filter', stateKey: 'disabledFilterIndexes' } },
  { urlKey: 'view', stateKey: 'views', disabled: { urlKey: 'disabled_view', stateKey: 'disabledViewIndexes' } },
  { urlKey: 'index', stateKey: 'indexes' }
];

const ARRAY_URL_KEYS = new Set(ARRAY_PARAMS.flatMap(p => [p.urlKey, p.disabled?.urlKey]).filter(notNil));

const WRITE_DELAY_MS = 100;

/**
 * Helper function to convert a number/string representation of a number into a valid offset.
 * @returns
 */
const parseOffset = (_offset: string | number | null) => {
  if (typeof _offset === 'number') {
    return _offset;
  }

  if (!_offset) {
    return 0;
  }

  const candidate = parseInt(_offset);
  return isNaN(candidate) ? 0 : candidate;
};

/**
 * Helper function to determine the selected value based on URL params and route context.
 */
const getSelectedValue = (params: URLSearchParams, pathname: string, bundleId?: string): string | null => {
  if (params.has('selected')) {
    return params.get('selected');
  }
  if (pathname.startsWith('/bundles') && bundleId) {
    return bundleId;
  }
  return null;
};

/**
 * Returns stable list handlers, keeping disabled positions attached through edits,
 * deduplication and removal. Lists without disabled metadata ignore enable/disable.
 */
const useListHandlers = <T,>(key: ListKey, _setValues: Dispatch<SetStateAction<SearchValues>>) => {
  const disabledKey = ARRAY_PARAMS.find(param => param.stateKey === key)?.disabled?.stateKey;
  const update = useCallback(
    (current: SearchValues, items: T[], disabledIndexes = disabledKey ? current[disabledKey] : []) => {
      if (!disabledKey) {
        return { ...current, [key]: items };
      }

      const normalized = normalizeList(items, disabledIndexes);
      return isEqual(normalized.items, current[key]) && isEqual(normalized.disabledIndexes, current[disabledKey])
        ? current
        : { ...current, [key]: normalized.items, [disabledKey]: normalized.disabledIndexes };
    },
    [key, disabledKey]
  );

  const add = useCallback(
    (item: T) => _setValues(c => update(c, uniq([...(c[key] as T[]), item]))),
    [_setValues, key, update]
  );

  const remove = useCallback(
    (item: T) =>
      _setValues(c => {
        const arr = c[key] as T[];
        const i = arr.indexOf(item);
        if (i === -1) {
          return c;
        }
        const disabledIndexes = (disabledKey ? c[disabledKey] : []).flatMap(index =>
          index === i ? [] : [index > i ? index - 1 : index]
        );
        return update(
          c,
          arr.filter((_, idx) => idx !== i),
          disabledIndexes
        );
      }),
    [_setValues, key, disabledKey, update]
  );

  const setAt = useCallback(
    (pos: number, item: T) =>
      _setValues(c => {
        const arr = c[key] as T[];
        if (!Number.isInteger(pos) || pos < 0 || pos >= arr.length) {
          return c;
        }
        const next = [...arr] as T[];
        next[pos] = item;
        return update(c, next);
      }),
    [_setValues, key, update]
  );

  const setAll = useCallback((items: T[]) => _setValues(c => update(c, uniq(items), [])), [_setValues, update]);

  const reset = useCallback(
    (defaultValue: T[] = []) => _setValues(c => update(c, defaultValue, [])),
    [_setValues, update]
  );

  const setDisabled = useCallback(
    (index: number, disabled: boolean) => {
      if (!disabledKey) {
        return;
      }
      _setValues(c => {
        if (!Number.isInteger(index) || index < 0 || index >= c[key].length) {
          return c;
        }
        const disabledIndexes = c[disabledKey];
        if (disabledIndexes.includes(index) === disabled) {
          return c;
        }
        return update(
          c,
          c[key] as T[],
          disabled ? [...disabledIndexes, index] : disabledIndexes.filter(position => position !== index)
        );
      });
    },
    [_setValues, key, disabledKey, update]
  );

  const enable = useCallback((index: number) => setDisabled(index, false), [setDisabled]);
  const disable = useCallback((index: number) => setDisabled(index, true), [setDisabled]);

  return { add, remove, setAt, setAll, reset, enable, disable };
};

const normalizeList = <T,>(items: T[], disabledIndexes: number[]) => {
  const indexesByItem = new Map<T, number>();
  const normalizedItems: T[] = [];
  const normalizedDisabled: boolean[] = [];

  items.forEach((item, index) => {
    const normalizedIndex = indexesByItem.get(item);
    const isDisabled = disabledIndexes.includes(index);
    if (normalizedIndex === undefined) {
      const nextIndex = normalizedItems.length;
      indexesByItem.set(item, nextIndex);
      normalizedItems.push(item);
      normalizedDisabled[nextIndex] = isDisabled;
      return;
    }

    normalizedDisabled[normalizedIndex] = normalizedDisabled[normalizedIndex] && isDisabled;
  });

  return {
    items: normalizedItems,
    disabledIndexes: normalizedDisabled.flatMap((isDisabled, index) => (isDisabled ? [index] : []))
  };
};

const getListFromUrl = (params: URLSearchParams, { urlKey, disabled }: ArrayParamDescriptor) => {
  const rawItems = params.getAll(urlKey);
  const disabledCounts = new Map<string, number>();
  const itemCounts = new Map<string, number>();

  (disabled ? params.getAll(disabled.urlKey) : []).forEach(item => {
    disabledCounts.set(item, (disabledCounts.get(item) ?? 0) + 1);
  });
  rawItems.forEach(item => {
    itemCounts.set(item, (itemCounts.get(item) ?? 0) + 1);
  });

  const items = uniq(rawItems);
  return {
    items,
    disabledIndexes: items.flatMap((item, index) =>
      (disabledCounts.get(item) ?? 0) >= (itemCounts.get(item) ?? 0) ? [index] : []
    )
  };
};

const getListStateFromUrl = (params: URLSearchParams, defaults: Partial<SearchValues>) =>
  Object.fromEntries(
    ARRAY_PARAMS.flatMap(descriptor => {
      const { items, disabledIndexes } = getListFromUrl(params, descriptor);
      const resolved = descriptor.stateKey === 'indexes' && isEmpty(items) ? defaults.indexes : items;
      return [
        [descriptor.stateKey, resolved],
        ...(descriptor.disabled ? [[descriptor.disabled.stateKey, disabledIndexes]] : [])
      ];
    })
  ) as Pick<SearchValues, ListKey | DisabledListKey>;

/**
 * Synchronizes SearchValues state with the URL search string, and vice-versa.
 */
const useUrlSync = (
  values: SearchValues,
  defaults: Partial<SearchValues>,
  _setValues: Dispatch<SetStateAction<SearchValues>>,
  params: URLSearchParams,
  setParams: ReturnType<typeof useSearchParams>[1],
  pathname: string,
  search: string,
  routeId?: string
) => {
  const lastProcessedLocation = useRef({ pathname, search, routeId });

  const getUrlFromState = useCallback(() => {
    const changes: Record<string, unknown> = {};

    // Scalar params: write if changed from URL, remove if back to default
    PARAM_MAPPINGS.forEach(([urlKey, stateKey]) => {
      const stateValue = values[stateKey];
      const urlValue = params.get(urlKey);
      if (stateValue === urlValue) {
        return;
      }

      if (params.has(urlKey) && stateValue === defaults[stateKey]) {
        changes[urlKey] = null; // remove
      } else if (stateValue !== defaults[stateKey]) {
        changes[urlKey] = stateValue; // write
      }
    });

    // Array params: skip when state equals default and URL is already empty
    ARRAY_PARAMS.forEach(({ urlKey, stateKey, disabled }) => {
      const { items: stateArr, disabledIndexes } = disabled
        ? normalizeList<string>(values[stateKey], values[disabled.stateKey])
        : { items: values[stateKey], disabledIndexes: [] };
      const urlArr = params.getAll(urlKey);
      const defaultValue = stateKey === 'indexes' ? defaults.indexes : undefined;
      if (!isEqual(stateArr, urlArr)) {
        const isDefault = defaultValue ? isEqual(stateArr, defaultValue) : stateArr.length === 0;
        if (!isDefault) {
          changes[urlKey] = stateArr.length === 0 ? null : stateArr;
        } else if (urlArr.length > 0) {
          changes[urlKey] = null; // state is default but URL isn't — remove
        }
      }

      // Keep every definition in the URL, with disabled entries marked separately.
      if (disabled) {
        const disabledParams = disabledIndexes.map(index => stateArr[index]);
        if (!isEqual(disabledParams, params.getAll(disabled.urlKey))) {
          changes[disabled.urlKey] = disabledParams.length === 0 ? null : disabledParams;
        }
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
  }, [values, defaults, params, pathname]);

  const getStateFromUrl = useCallback(() => {
    const changes: Partial<SearchValues> = {};
    const listState = getListStateFromUrl(params, defaults);

    // Scalar params: fall back to default when absent from URL
    PARAM_MAPPINGS.forEach(([urlKey, stateKey]) => {
      const urlValue = params.has(urlKey)
        ? params.get(urlKey)
        : stateKey === 'startDate' || stateKey === 'endDate'
          ? null
          : (defaults[stateKey] ?? undefined);
      if (urlValue !== values[stateKey]) {
        (changes as any)[stateKey] = urlValue;
      }
    });

    // Array params: fall back to their declared default when absent from URL
    Object.entries(listState).forEach(([key, value]) => {
      if (!isEqual(value, values[key as keyof typeof listState])) {
        (changes as any)[key] = value;
      }
    });

    // selected
    const selectedValue = getSelectedValue(params, pathname, routeId);
    if (selectedValue !== values.selected) {
      changes.selected = selectedValue;
    }

    // offset
    const urlOffset = parseOffset(params.get('offset'));
    if (urlOffset !== values.offset) {
      changes.offset = urlOffset;
    }

    return omitBy(omitBy(changes, isUndefined), (val, key) => val == (values as any)[key]);
  }, [values, defaults, params, pathname, routeId]);

  // State → URL
  useEffect(() => {
    if (!isEqual(lastProcessedLocation.current, { pathname, search, routeId })) {
      return;
    }

    const changes = getUrlFromState();
    if (isEmpty(changes)) {
      return;
    }

    setParams(
      _params => {
        const newParams = new URLSearchParams(_params);
        Object.entries(changes).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            newParams.delete(key);
            (value as string[]).forEach(val => newParams.append(key, val));
          } else if (isNil(value)) {
            newParams.delete(key);
          } else {
            newParams.set(key, String(value));
          }
        });
        return newParams;
      },
      { replace: !changes.query && !has(changes, 'offset') }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values]);

  // URL → State
  useEffect(() => {
    lastProcessedLocation.current = { pathname, search, routeId };
    const changes = getStateFromUrl();
    if (isEmpty(changes)) {
      return;
    }
    _setValues(c => ({ ...c, ...changes }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, pathname, routeId]);
};

/**
 * Context responsible for tracking updates to query operations in hit and view search.
 */
const ParameterProvider: FC<PropsWithChildren<{ defaults?: Partial<SearchValues> }>> = ({
  children,
  defaults: _defaults = {}
}) => {
  const location = useLocation();
  const routeParams = useParams();
  const [params, setParams] = useSearchParams();

  const defaults = useMemo<Partial<SearchValues>>(() => ({ ...DEFAULT_VALUES, ..._defaults }), [_defaults]);

  const pendingChanges = useRef<Partial<SearchValues>>({});
  const writeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [values, _setValues] = useState<SearchValues>({
    selected: getSelectedValue(params, location.pathname, routeParams.id),
    query: params.get('query') ?? defaults.query!,
    sort: params.get('sort') ?? defaults.sort!,
    span: params.get('span') ?? defaults.span!,
    ...getListStateFromUrl(params, defaults),
    indexes: params.has('index') ? uniq(params.getAll('index') as SearchIndex[]).filter(identity) : defaults.indexes!,
    startDate: params.get('start_date'),
    endDate: params.get('end_date'),
    offset: parseOffset(params.get('offset')),
    trackTotalHits: (params.get('track_total_hits') ?? 'false') !== 'false'
  });

  useLayoutEffect(() => {
    if (writeTimeout.current !== null) {
      clearTimeout(writeTimeout.current);
      writeTimeout.current = null;
    }
    pendingChanges.current = {};

    return () => {
      if (writeTimeout.current !== null) {
        clearTimeout(writeTimeout.current);
        writeTimeout.current = null;
      }
    };
  }, [location.pathname, location.search, routeParams.id]);

  // TODO: SELECTING A BUNDLE STILL CAUSES A FREAKOUT
  useUrlSync(values, defaults, _setValues, params, setParams, location.pathname, location.search, routeParams.id);

  const set = useCallback(
    <K extends keyof SearchValues>(key: K) =>
      (value: SearchValues[K]) => {
        if (value === values[key]) {
          return;
        }

        if (key === 'selected') {
          pendingChanges.current.selected = value as SearchValues['selected'];
        } else {
          (pendingChanges.current as any)[key] = value ?? defaults[key] ?? null;
        }

        if (key === 'span' && typeof value === 'string' && !value.endsWith('custom')) {
          pendingChanges.current.startDate = null;
          pendingChanges.current.endDate = null;
        }

        if (writeTimeout.current !== null) {
          clearTimeout(writeTimeout.current);
        }
        writeTimeout.current = setTimeout(() => {
          writeTimeout.current = null;
          const changes = pendingChanges.current;
          pendingChanges.current = {};
          _setValues(c => ({ ...c, ...changes }));
        }, WRITE_DELAY_MS);
      },
    [values, defaults]
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
        enableFilter: filters.enable,
        disableFilter: filters.disable,
        resetFilters: filters.reset,

        addIndex: indexes.add,
        removeIndex: indexes.remove,
        setIndex: indexes.setAt,
        setIndexes: indexes.setAll,
        resetIndexes: useCallback(() => indexes.reset(defaults.indexes), [indexes, defaults]),

        addView: views.add,
        removeView: views.remove,
        setView: views.setAt,
        enableView: views.enable,
        disableView: views.disable,
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
