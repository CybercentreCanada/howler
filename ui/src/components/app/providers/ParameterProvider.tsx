import { isEmpty, isNull, isUndefined, omitBy, pickBy } from 'lodash-es';
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
  filter?: string;
  startDate?: string;
  endDate?: string;

  setSelected: (id: string) => void;
  setQuery: (id: string) => void;
  setOffset: (offset: string | number) => void;
  setSort: (sort: string) => void;
  setSpan: (span: string) => void;
  setFilter: (filter: string) => void;
  setCustomSpan: (startDate: string, endDate: string) => void;
}

interface SearchValues {
  selected: string;
  query: string;
  sort: string;
  span: string;
  filter: string;
  startDate: string;
  endDate: string;
  offset: number;
  trackTotalHits: boolean;
}

export const ParameterContext = createContext<ParameterProviderType>(null);

const DEFAULT_VALUES = {
  query: DEFAULT_QUERY,
  sort: 'event.created desc',
  span: 'date.range.1.month'
};

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
 * Context responsible for tracking updates to query operations in hit and view search.
 */
const ParameterProvider: FC<PropsWithChildren> = ({ children }) => {
  const location = useLocation();
  const routeParams = useParams();
  const [params, setParams] = useSearchParams();

  const pendingChanges = useRef<Partial<SearchValues>>({});

  const [values, _setValues] = useState<SearchValues>({
    selected: params.get('selected'),
    query: params.get('query') ?? DEFAULT_VALUES.query,
    sort: params.get('sort') ?? DEFAULT_VALUES.sort,
    span: params.get('span') ?? DEFAULT_VALUES.span,
    filter: params.get('filter'),
    startDate: params.get('start_date'),
    endDate: params.get('end_date'),
    offset: parseOffset(params.get('offset')),
    trackTotalHits: (params.get('track_total_hits') ?? 'false') !== 'false'
  });

  // TODO: SELECTING A BUNDLE STILL CAUSES A FREAKOUT

  const set = useCallback(
    (key: keyof SearchValues) => value => {
      if (value === values[key]) {
        return;
      }

      if (key === 'selected' && !value && location.pathname.startsWith('/bundles')) {
        pendingChanges.current[key] = routeParams.id;
      } else {
        (pendingChanges.current as any)[key] = value ?? DEFAULT_VALUES[key] ?? null;
      }

      if (key === 'span' && !value.endsWith('custom')) {
        pendingChanges.current.startDate = null;
        pendingChanges.current.endDate = null;
      }

      WRITE_THROTTLER.debounce(() => {
        _setValues(_current => ({ ..._current, ...pendingChanges.current }));
        pendingChanges.current = {};
      });
    },
    [location.pathname, routeParams.id, values]
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

  const getDiff = useCallback(
    (operation: 'read' | 'write') => {
      /**
       * A record of changes necessary to synchronize the query string and the internal values store.
       */
      const changes: Partial<SearchValues> = {};

      const standardKeys = [
        ['query', values.query],
        ['sort', values.sort],
        ['span', values.span],
        ['filter', values.filter],
        ['start_date', values.startDate],
        ['end_date', values.endDate]
      ];

      standardKeys.forEach(([key, value]) => {
        // Get the value from the URL, using the default values as fallback (and set to undefined if neither is set)
        const fromSearchWithFallback = params.has(key) ? params.get(key) : (DEFAULT_VALUES[key] ?? undefined);

        // If there's a difference between the search value and the value in the internal store, we append the key and new value to changes
        // This is based on the operation
        if (fromSearchWithFallback !== value) {
          changes[key] = operation === 'write' ? value : fromSearchWithFallback;
        }

        // This is where things get a bit tricky. We use the fact that undefined and null are different concepts in Javascript here
        // "undefined" is later filtered out, meaning "no change", while null means "remove this value"
        if (operation === 'write') {
          // If the change is to just set it to default in the query string, set it to null to just remove that entry altogether
          // Due to the DEFAULT_VALUES check in fromSearchWithFallback above, this will use the defeault value.
          // i.e., this has the same effect, but cleans up the query string
          if (params.has(key) && !isUndefined(changes[key]) && changes[key] === DEFAULT_VALUES[key]) {
            changes[key] = null;
          }
        }
      });

      // Logic for the selected key - this can vary depending on the context
      if (operation === 'write') {
        // Are we in a bundle, with a selected parameter?
        // If so, does it match the bundle ID? If so, it's redundant and should be removed
        if (
          location.pathname.startsWith('/bundles') &&
          (!params.has('selected') || values.selected === params.get('selected'))
        ) {
          changes.selected = null;
        } else {
          // We're either not in a bundle, or in a bundle and a hit different from the main bundle is selected
          changes.selected = values.selected;
        }
      } else {
        if (params.has('selected')) {
          // If we have a selected hit, that's the selected value to use
          changes.selected = params.get('selected');
        } else if (location.pathname.startsWith('/bundles')) {
          // If not, fallback to the bundle ID
          changes.selected = routeParams.id;
        } else {
          // Otherwise nothing has been selected
          changes.selected = null;
        }
      }

      if (parseOffset(params.get('offset')) !== values.offset) {
        changes.offset = operation === 'write' ? values.offset : parseOffset(params.get('offset'));

        // Same deal - if offset is 0, just remove it entirely (it'll default to 0 offset)
        if (operation === 'write' && !changes.offset) {
          changes.offset = null;
        }
      }

      // This is where we check for what has actually changed against the given store
      // We first omit undefined keys (fromSearchWithFallback can introduce these)
      // Then we omit any values that already match the store we're updating
      // (query string or internal state).
      return omitBy(omitBy(changes, isUndefined), (val, key) =>
        operation === 'write' ? val == params.get(key) : val == values[key]
      );
    },
    [values, params, location.pathname, routeParams.id]
  );

  /**
   * Effect to synchronize the context's state with the address bar
   */
  useEffect(() => {
    const changes = getDiff('write');

    if (!isEmpty(changes)) {
      const existingParams = Object.fromEntries(params.entries());

      setParams(
        _params => {
          const newParams = new URLSearchParams({ ...existingParams, ...(changes as Record<string, string>) });

          Object.entries(pickBy(changes, isNull)).forEach(([key]) => newParams.delete(key));

          return newParams;
        },
        { replace: !changes.query && !Object.keys(changes).includes('offset') }
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values]);

  useEffect(() => {
    const changes = getDiff('read');

    if (!isEmpty(changes)) {
      _setValues(_current => ({
        ..._current,
        ...changes
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, location.pathname, routeParams.id]);

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
        setFilter: useMemo(() => set('filter'), [set])
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
