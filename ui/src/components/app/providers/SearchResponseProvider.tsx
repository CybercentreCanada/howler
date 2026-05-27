import type { HowlerSearchResponse } from 'api/search';
import type { DispatchApiConfig } from 'components/hooks/useMyApi';
import useMyApi from 'components/hooks/useMyApi';
import { createContext, useCallback, useState, type PropsWithChildren } from 'react';

export type SearchResponseContextType<T> = {
  push: (item: T) => void;
  remove: (id: string) => void;
  replace: (id: string, item: T) => void;
  request: (apiCall: Promise<HowlerSearchResponse<T>>, config?: DispatchApiConfig) => Promise<HowlerSearchResponse<T>>;
  response: HowlerSearchResponse<T>;
};

export const SearchResponseContext = createContext<SearchResponseContextType<any>>(null);

type SearchResponseProviderProps = PropsWithChildren<{
  id_field: string;
}>;

const SearchResponseProvider = <T,>({ children, id_field }: SearchResponseProviderProps) => {
  const { dispatchApi } = useMyApi();
  const [response, setResponse] = useState<HowlerSearchResponse<T>>(null);

  const request = useCallback(
    async (apiCall: Promise<HowlerSearchResponse<T>>, config?: DispatchApiConfig) => {
      const _response = await dispatchApi(apiCall, config);
      setResponse(_response);
      return _response;
    },
    [dispatchApi]
  );

  const push = useCallback(
    (item: T) => {
      setResponse(_response => {
        const filteredItems = _response.items.filter(v => v[id_field] !== item[id_field]);
        const itemExists = filteredItems.length < _response.items.length;
        filteredItems.push(item);

        return {
          items: filteredItems.length <= _response.rows ? filteredItems : _response.items,
          offset: _response.offset,
          rows: _response.rows,
          total: itemExists ? _response.total : _response.total + 1
        };
      });
    },
    [id_field]
  );

  const replace = useCallback(
    (id: string, item: T) => {
      setResponse(_response => {
        return {
          items: _response.items.map(v => (v[id_field] === id ? item : v)),
          offset: _response.offset,
          rows: _response.rows,
          total: _response.total
        };
      });
    },
    [id_field]
  );

  const remove = useCallback(
    (id: string) => {
      setResponse(_response => {
        const filteredItems = _response.items.filter(v => v[id_field] !== id);
        const itemExists = filteredItems.length < _response.items.length;

        return {
          items: filteredItems,
          offset: _response.offset,
          rows: itemExists ? _response.rows - 1 : _response.rows,
          total: itemExists ? _response.total - 1 : _response.total
        };
      });
    },
    [id_field]
  );

  return (
    <SearchResponseContext.Provider value={{ push, remove, replace, request, response }}>
      {children}
    </SearchResponseContext.Provider>
  );
};

export default SearchResponseProvider;
