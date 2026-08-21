import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import type { DispatchApiConfig } from 'components/hooks/useMyApi';
import useMyApi from 'components/hooks/useMyApi';
import { createContext, useCallback, useContext, useState, type Context, type PropsWithChildren } from 'react';

export type SearchResponseState<T> = HowlerSearchResponse<T> & {
  removeCount: number;
};

export type SearchResponseContextType<T> = {
  push: (item: T) => void;
  remove: (id: string) => void;
  replace: (id: string, item: T) => void;
  request: <Request extends HowlerSearchRequest>(
    endpoint: (request: Request) => Promise<HowlerSearchResponse<T> | null>,
    requestData: Request,
    config?: DispatchApiConfig
  ) => Promise<HowlerSearchResponse<T>>;
  getSearchRequestData: (requestData: Partial<HowlerSearchRequest>) => Partial<HowlerSearchRequest>;
  response: SearchResponseState<T> | null;
};

export type SearchResponseContext<T> = Context<SearchResponseContextType<T> | null>;

export const createSearchResponseContext = <T,>(): SearchResponseContext<T> =>
  createContext<SearchResponseContextType<T> | null>(null);

export const useSearchResponseContext = <T,>(context: SearchResponseContext<T>): SearchResponseContextType<T> => {
  const value = useContext(context);

  if (value === null) {
    throw new Error('useSearchResponseContext must be used within a SearchResponseProvider');
  }

  return value;
};

type SearchResponseProviderProps<T> = PropsWithChildren<{
  context: SearchResponseContext<T>;
  idField: string;
  initialResponse?: SearchResponseState<T> | null;
}>;

const SearchResponseProvider = <T,>({
  children,
  context,
  idField,
  initialResponse = null
}: SearchResponseProviderProps<T>) => {
  const { dispatchApi } = useMyApi();
  const [response, setResponse] = useState<SearchResponseState<T> | null>(initialResponse);

  // T has no known shape, so the id field lookup has to go through an untyped index access.
  const getFieldValue = useCallback((item: T): unknown => (item as Record<string, unknown>)[idField], [idField]);

  const request = useCallback(
    async <Request extends HowlerSearchRequest>(
      endpoint: (request: Request) => Promise<HowlerSearchResponse<T> | null>,
      requestData: Request,
      config?: DispatchApiConfig
    ) => {
      const _response = await dispatchApi(endpoint(requestData), config);
      const searchResponse = _response ?? {
        items: [],
        offset: requestData.offset ?? 0,
        rows: requestData.rows ?? 0,
        total: 0
      };

      setResponse(_prevResponse => ({
        ...searchResponse,
        removeCount: searchResponse.offset <= (_prevResponse?.offset ?? 0) ? 0 : (_prevResponse?.removeCount ?? 0)
      }));
      return searchResponse;
    },
    [dispatchApi]
  );

  const getSearchRequestData = useCallback(
    (requestData: Partial<HowlerSearchRequest>) => {
      const modifiedRequest = { ...requestData };

      if (response?.removeCount) {
        if (
          response.offset !== undefined &&
          modifiedRequest.offset !== undefined &&
          response.offset < modifiedRequest.offset
        ) {
          modifiedRequest.offset = Math.max(0, modifiedRequest.offset - response.removeCount);
        }
      }

      return modifiedRequest;
    },
    [response]
  );

  const push = useCallback(
    (item: T) => {
      setResponse(_response => {
        if (_response === null) {
          return _response;
        }

        const filteredItems = _response.items.filter(v => getFieldValue(v) !== getFieldValue(item));
        const itemExists = filteredItems.length < _response.items.length;
        filteredItems.push(item);

        return {
          items: filteredItems.length <= _response.rows ? filteredItems : _response.items,
          offset: _response.offset,
          rows: _response.rows,
          total: itemExists ? _response.total : _response.total + 1,
          removeCount: itemExists ? _response.removeCount : Math.max(_response.removeCount - 1, 0)
        };
      });
    },
    [getFieldValue]
  );

  const replace = useCallback(
    (id: string, item: T) => {
      if (getFieldValue(item) !== undefined && id !== getFieldValue(item)) {
        throw new Error('Item id is defined but id does not match the id provided to replace function');
      }

      const newItem = {
        ...item,
        [idField]: getFieldValue(item) !== undefined ? getFieldValue(item) : id
      };

      setResponse(_response => {
        if (_response === null) {
          return _response;
        }
        return {
          items: _response.items.map(v => (getFieldValue(v) === id ? newItem : v)),
          offset: _response.offset,
          rows: _response.rows,
          total: _response.total,
          removeCount: _response.removeCount
        };
      });
    },
    [idField, getFieldValue]
  );

  const remove = useCallback(
    (id: string) => {
      setResponse(_response => {
        if (_response === null) {
          return _response;
        }
        const filteredItems = _response.items.filter(v => getFieldValue(v) !== id);
        const itemExists = filteredItems.length < _response.items.length;

        return {
          items: filteredItems,
          offset: _response.offset,
          rows: _response.rows,
          total: itemExists ? _response.total - 1 : _response.total,
          removeCount: itemExists ? _response.removeCount + 1 : _response.removeCount
        };
      });
    },
    [getFieldValue]
  );

  const Provider = context.Provider;

  return <Provider value={{ push, remove, replace, request, getSearchRequestData, response }}>{children}</Provider>;
};

export default SearchResponseProvider;
