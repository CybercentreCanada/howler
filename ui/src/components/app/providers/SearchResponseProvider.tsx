import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import type { DispatchApiConfig } from 'components/hooks/useMyApi';
import useMyApi from 'components/hooks/useMyApi';
import { createContext, useCallback, useState, type PropsWithChildren } from 'react';

export type SearchResponseState<T> = HowlerSearchResponse<T> & {
  removeCount: number;
};

export type SearchResponseContextType<T> = {
  push: (item: T) => void;
  remove: (id: string) => void;
  replace: (id: string, item: T) => void;
  request: (
    endpoint: (request: HowlerSearchRequest) => Promise<HowlerSearchResponse<T>>,
    request_data: HowlerSearchRequest,
    config?: DispatchApiConfig
  ) => Promise<HowlerSearchResponse<T>>;
  getSearchRequestData: (request_data: Partial<HowlerSearchRequest>) => Partial<HowlerSearchRequest>;
  response: SearchResponseState<T>;
};

export const SearchResponseContext = createContext<SearchResponseContextType<any>>(null);

type SearchResponseProviderProps<T> = PropsWithChildren<{
  id_field: string;
  initialResponse?: SearchResponseState<T>;
}>;

const SearchResponseProvider = <T,>({ children, id_field, initialResponse = null }: SearchResponseProviderProps<T>) => {
  const { dispatchApi } = useMyApi();
  const [response, setResponse] = useState<SearchResponseState<T>>(initialResponse);

  const request = useCallback(
    async (
      endpoint: (request: HowlerSearchRequest) => Promise<HowlerSearchResponse<T>>,
      request_data: HowlerSearchRequest,
      config?: DispatchApiConfig
    ) => {
      const _response = await dispatchApi(endpoint(request_data), config);

      setResponse({
        ..._response,
        removeCount: _response.offset <= response?.offset ? 0 : (response?.removeCount ?? 0)
      });
      return _response;
    },
    [dispatchApi, response]
  );

  const getSearchRequestData = useCallback(
    (request_data: Partial<HowlerSearchRequest>) => {
      const modifiedRequest = { ...request_data };

      if (response?.removeCount) {
        if (response.offset < modifiedRequest.offset) {
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

        const filteredItems = _response.items.filter(v => v[id_field] !== item[id_field]);
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
    [id_field]
  );

  const replace = useCallback(
    (id: string, item: T) => {
      if (item[id_field] !== undefined && id !== item[id_field]) {
        throw new Error('Item id is defined but id does not match the id provided to replace function');
      }

      const newItem = {
        ...item,
        [id_field]: item[id_field] !== undefined ? item[id_field] : id
      };

      setResponse(_response => {
        if (_response === null) {
          return _response;
        }
        return {
          items: _response.items.map(v => (v[id_field] === id ? newItem : v)),
          offset: _response.offset,
          rows: _response.rows,
          total: _response.total,
          removeCount: _response.removeCount
        };
      });
    },
    [id_field]
  );

  const remove = useCallback(
    (id: string) => {
      setResponse(_response => {
        if (_response === null) {
          return _response;
        }
        const filteredItems = _response.items.filter(v => v[id_field] !== id);
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
    [id_field]
  );

  return (
    <SearchResponseContext.Provider value={{ push, remove, replace, request, getSearchRequestData, response }}>
      {children}
    </SearchResponseContext.Provider>
  );
};

export default SearchResponseProvider;
