import api from 'api';
import type { SearchField } from 'api/search/fields';
import useMyApi from 'components/hooks/useMyApi';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useRef, useState } from 'react';

interface FieldContextType {
  hitFields: SearchField[];
  getHitFields: () => Promise<SearchField[]>;
}

export const FieldContext = createContext<FieldContextType>(null!);

const FieldProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();

  const [hitFields, setHitFields] = useState<SearchField[]>([]);
  const hitFieldsCache = useRef<SearchField[] | null>(null);
  const hitFieldsRequest = useRef<Promise<SearchField[]> | null>(null);

  const getHitFields = useCallback(() => {
    if (hitFieldsCache.current) {
      return Promise.resolve(hitFieldsCache.current);
    }

    if (hitFieldsRequest.current) {
      return hitFieldsRequest.current;
    }

    const request = dispatchApi(api.search.fields.hit.get())
      .then(fields => {
        const resolvedFields = fields ?? [];
        hitFieldsCache.current = resolvedFields;
        setHitFields(resolvedFields);
        return resolvedFields;
      })
      .finally(() => {
        hitFieldsRequest.current = null;
      });

    hitFieldsRequest.current = request;
    return request;
  }, [dispatchApi]);

  return <FieldContext.Provider value={{ hitFields, getHitFields }}>{children}</FieldContext.Provider>;
};

export default FieldProvider;
