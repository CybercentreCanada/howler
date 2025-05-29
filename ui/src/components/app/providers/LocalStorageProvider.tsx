import useLocalStorage from 'commons/components/utils/hooks/useLocalStorage';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useEffect, useState } from 'react';
import { MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';

type ValuesType = { [K in StorageKey]?: any };

interface LocalStorageContextType {
  set: <T>(key: string, value: T) => void;
  values: ValuesType;
  remove: (key: string) => void;
}

export const LocalStorageContext = createContext<LocalStorageContextType>(null);

const LocalStorageProvider: FC<PropsWithChildren> = ({ children }) => {
  const { get: getStored, set: setStored, remove: removeStored } = useLocalStorage(MY_LOCAL_STORAGE_PREFIX);

  const [values, setValues] = useState<ValuesType>({});

  useEffect(() => {
    const newData: ValuesType = {};

    for (const key in StorageKey) {
      if (!values[StorageKey[key]]) {
        newData[StorageKey[key]] = getStored(StorageKey[key]);
      }
    }

    setValues(current => {
      return {
        ...current,
        ...newData
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getStored]);

  const set: LocalStorageContextType['set'] = useCallback(
    (key, value) => {
      setStored(key, value);
      setValues(current => ({
        ...current,
        [key]: value
      }));
    },
    [setStored]
  );

  const remove: LocalStorageContextType['remove'] = useCallback(
    (key: string) => {
      removeStored(key);
      setValues(current => {
        const copy = { ...current };

        delete copy[key];

        return copy;
      });
    },
    [removeStored]
  );

  return <LocalStorageContext.Provider value={{ values, set, remove }}>{children}</LocalStorageContext.Provider>;
};

export default LocalStorageProvider;
