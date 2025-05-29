import api from 'api';
import type { SearchField } from 'api/search/fields';
import useMyApi from 'components/hooks/useMyApi';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useState } from 'react';

interface FieldProviderType {
  hitFields: SearchField[];
  getHitFields: () => Promise<SearchField[]>;
}

export const FieldContext = createContext<FieldProviderType>(null);

const FieldProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();

  const [hitFields, setHitFields] = useState<SearchField[]>([]);

  const getHitFields = useCallback(async () => {
    if (hitFields.length) {
      return hitFields;
    }

    const fields = await dispatchApi(api.search.fields.hit.get());

    setHitFields(fields);

    return fields;
  }, [dispatchApi, hitFields]);

  return <FieldContext.Provider value={{ hitFields, getHitFields }}>{children}</FieldContext.Provider>;
};

export default FieldProvider;
