import { isEmpty, isEqual, isUndefined, omitBy } from 'lodash-es';
import type { FC, PropsWithChildren } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useParams, useSearchParams } from 'react-router-dom';
import { createContext, useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY } from 'utils/constants';
import Throttler from 'utils/Throttler';

interface ParameterProviderType {
  selected?: string;
  query?: string;
  offset: number;
  trackTotalHits: boolean;
  sort?: string;
  span?: string;
  filters?: string[];
  startDate?: string;
  endDate?: string;

  setSelected: (id: string) => void;
  setQuery: (id: string) => void;
  setOffset: (offset: string | number) => void;
  setSort: (sort: string) => void;
  setSpan: (span: string) => void;
  addFilter: (filter: string) => void;
  removeFilter: (filter: string) => void;
  clearFilters: () => void;
  setCustomSpan: (startDate: string, endDate: string) => void;
}

interface SearchValues {
  selected: string;
  query: string;
  sort: string;
  span: string;
  filters: string[];
  startDate: string;
  endDate: string;
  offset: number;
  trackTotalHits: boolean;
}

export const ParameterContext = createContext<ParameterProviderType>(null);

const DEFAULT_VALUES: Partial<SearchValues> = {
  query: DEFAULT_QUERY,
  sort: 'event.created desc',
  span: 'date.range.1.month'
};

/**
 * Mapping of URL parameter keys to internal state keys
 * Note: 'filters' is handled separately due to multi-value support
 */
const PARAM_MAPPINGS: [string, keyof SearchValues][] = [
  ['query', 'query'],
  ['sort', 'sort'],
  ['span', 'span'],
  ['start_date', 'startDate'],
  ['end_date', 'endDate']
];

const WRITE_THROTTLER = new Throttler(100);

/**
 * Helper function to convert a number/string representation of a number into a valid offset.
 * @returns
 */
const parseOffset = (_offset: string | number) => {
  if (typeof _offset === 'number') {
    return _offset;
  }

  const candidate = parseInt(_offset);
  return isNaN(candidate) ? 0 : candidate;
};

/**
 * Helper function to determine the selected value based on URL params and route context.
 */
const getSelectedValue = (params: URLSearchParams, pathname: string, bundleId?: string) => {
  if (params.has('selected')) {
    return params.get('selected');
  }

  if (pathname.startsWith('/bundles') && bundleId) {
    return bundleId;
  }

  return null;
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
    filters: params.getAll('filter'),
    startDate: params.get('start_date'),
    endDate: params.get('end_date'),
    offset: parseOffset(params.get('offset')),
    trackTotalHits: (params.get('track_total_hits') ?? 'false') !== 'false'
  });

  // TODO: SELECTING A BUNDLE STILL CAUSES A FREAKOUT

  const set: <K extends Exclude<keyof SearchValues, 'filters'>>(key: K) => (value: SearchValues[K]) => void =
    useCallback(
      key => value => {
        if ((key as string) === 'filters') {
          console.error('Cannot use set() for filters. Use addFilter/removeFilter/clearFilters instead.');
          return;
        }

        if (value === values[key]) {
          return;
        }

        if (key === 'selected' && !value) {
          pendingChanges.current.selected = getSelectedValue(params, location.pathname, routeParams.id);
        } else {
          (pendingChanges.current as any)[key] = value ?? DEFAULT_VALUES[key] ?? null;
        }

        if (key === 'span' && typeof value === 'string' && !value.endsWith('custom')) {
          pendingChanges.current.startDate = null;
          pendingChanges.current.endDate = null;
        }

        WRITE_THROTTLER.debounce(() => {
          _setValues(_current => ({ ..._current, ...pendingChanges.current }));
          pendingChanges.current = {};
        });
      },
      [location.pathname, routeParams.id, values, params]
    );

  const setOffset: ParameterProviderType['setOffset'] = useCallback(
    _offset => _setValues(_current => ({ ..._current, offset: parseOffset(_offset) })),
    []
  );

  const setCustomSpan: ParameterProviderType['setCustomSpan'] = useCallback((startDate, endDate) => {
    _setValues(_values => ({
      ..._values,
      startDate,
      endDate
    }));
  }, []);

  const addFilter: ParameterProviderType['addFilter'] = useCallback(filter => {
    _setValues(_current => ({
      ..._current,
      filters: [..._current.filters, filter]
    }));
  }, []);

  const removeFilter: ParameterProviderType['removeFilter'] = useCallback(filter => {
    _setValues(_current => {
      const index = _current.filters.indexOf(filter);
      if (index === -1) {
        return _current;
      }
      return {
        ..._current,
        filters: _current.filters.filter((_, i) => i !== index)
      };
    });
  }, []);

  const clearFilters: ParameterProviderType['clearFilters'] = useCallback(() => {
    _setValues(_current => ({
      ..._current,
      filters: []
    }));
  }, []);

  /**
   * Get URL parameter changes needed to sync internal state to the address bar.
   * Returns null values for params that should be removed from URL.
   */
  const getUrlFromState = useCallback(() => {
    const changes: Partial<SearchValues> = {};

    PARAM_MAPPINGS.forEach(([urlKey, stateKey]) => {
      const stateValue = values[stateKey];
      const urlValue = params.get(urlKey);

      if (stateValue !== urlValue) {
        // If the value matches the default, remove it from URL (null signals removal)
        if (params.has(urlKey) && stateValue === DEFAULT_VALUES[stateKey]) {
          (changes as any)[urlKey] = null;
        } else {
          (changes as any)[urlKey] = stateValue;
        }
      }
    });

    // Handle filters: compare arrays with isEqual
    const urlFilters = params.getAll('filter');
    if (!isEqual(values.filters, urlFilters)) {
      // Coerce empty array to null for removal signal
      (changes as any).filters = values.filters.length === 0 ? null : values.filters;
    }

    // Handle selected: remove if redundant in bundle context, otherwise set
    if (
      location.pathname.startsWith('/bundles') &&
      (!params.has('selected') || values.selected === params.get('selected'))
    ) {
      changes.selected = null;
    } else if (values.selected !== params.get('selected')) {
      changes.selected = values.selected;
    }

    // Handle offset: remove if 0, otherwise set
    const urlOffset = parseOffset(params.get('offset'));
    if (urlOffset !== values.offset) {
      changes.offset = values.offset || null;
    }

    // Filter out values that already match the URL (skip 'filters' as it's handled above)
    return omitBy(changes, (val, key) => {
      if (key === 'filters') {
        return false; // Don't filter out filters, we already handled it
      }
      return val == params.get(key);
    });
  }, [values, params, location.pathname]);

  /**
   * Get state changes needed to sync URL parameters to internal state.
   */
  const getStateFromUrl = useCallback(() => {
    const changes: Partial<SearchValues> = {};

    PARAM_MAPPINGS.forEach(([urlKey, stateKey]) => {
      const urlValue = params.has(urlKey) ? params.get(urlKey) : (DEFAULT_VALUES[stateKey] ?? undefined);

      if (urlValue !== values[stateKey]) {
        (changes as any)[stateKey] = urlValue;
      }
    });

    // Handle filters: compare arrays with isEqual
    const urlFilters = params.getAll('filter');
    if (!isEqual(urlFilters, values.filters)) {
      changes.filters = urlFilters;
    }

    // Handle selected using helper
    const selectedValue = getSelectedValue(params, location.pathname, routeParams.id);
    if (selectedValue !== values.selected) {
      changes.selected = selectedValue;
    }

    // Handle offset
    const urlOffset = parseOffset(params.get('offset'));
    if (urlOffset !== values.offset) {
      changes.offset = urlOffset;
    }

    // Filter out undefined values and values that already match state
    return omitBy(omitBy(changes, isUndefined), (val, key) => val == values[key]);
  }, [values, params, location.pathname, routeParams.id]);

  /**
   * Effect to synchronize the context's state with the address bar
   */
  useEffect(() => {
    const changes = getUrlFromState();

    if (isEmpty(changes)) {
      return;
    }

    setParams(
      _params => {
        // Build fresh URLSearchParams from existing params
        const newParams = new URLSearchParams(_params);

        // Handle standard params
        Object.entries(changes).forEach(([key, value]) => {
          if (key === 'filters') {
            // Special handling for filters array
            newParams.delete('filter');
            if (Array.isArray(value)) {
              value.forEach(filter => newParams.append('filter', filter));
            }
            // null/undefined means remove (already deleted above)
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

  useEffect(() => {
    const changes = getStateFromUrl();

    if (isEmpty(changes)) {
      return;
    }

    _setValues(_current => ({
      ..._current,
      ...changes
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, location.pathname, routeParams.id]);

  return (
    <ParameterContext.Provider
      value={{
        ...values,

        setOffset,
        setCustomSpan,
        addFilter,
        removeFilter,
        clearFilters,

        setSelected: useMemo(() => set('selected'), [set]),
        setQuery: useMemo(() => set('query'), [set]),
        setSort: useMemo(() => set('sort'), [set]),
        setSpan: useMemo(() => set('span'), [set])
      }}
    >
      {children}
    </ParameterContext.Provider>
  );
};

export const useParameterContextSelector = <Selected,>(
  selector: (value: ParameterProviderType) => Selected
): Selected => {
  return useContextSelector<ParameterProviderType, Selected>(ParameterContext, selector);
};

export default ParameterProvider;
