import useLocalStorage from 'components/hooks/useLocalStorage';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useEffect, useState } from 'react';
import { MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';

type ValuesType = { [K in StorageKey]?: any };

export interface LocalStorageContextType {
  set: <T>(key: StorageKey, value: T) => void;
  values: ValuesType;
  remove: (key: StorageKey) => void;
}

export const LocalStorageContext = createContext<LocalStorageContextType>(null!);

const LocalStorageProvider: FC<PropsWithChildren> = ({ children }) => {
  const { get: getStored, set: setStored, remove: removeStored } = useLocalStorage(MY_LOCAL_STORAGE_PREFIX);

  const [values, setValues] = useState<ValuesType>({});

  useEffect(() => {
    const newData: ValuesType = {};

    for (const key in StorageKey) {
      const storageKey = StorageKey[key as keyof typeof StorageKey];

      if (!values[storageKey]) {
        newData[storageKey] = getStored(storageKey);
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
    key => {
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
