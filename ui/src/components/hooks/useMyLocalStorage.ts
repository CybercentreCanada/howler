import { LocalStorageContext, type LocalStorageContextType } from 'components/app/providers/LocalStorageProvider';
import { useContext } from 'react';
import type { StorageKey } from 'utils/constants';
import { MY_LOCAL_STORAGE_PREFIX } from 'utils/constants';
import useLocalStorage from './useLocalStorage';
import useLocalStorageItem, {
  type LocalStorageItemResult,
  type NonNullish,
  type WidenLiteral
} from './useLocalStorageItem';

const useMyLocalStorage = () => {
  return useLocalStorage(MY_LOCAL_STORAGE_PREFIX);
};

type UseMyLocalStorageItem = {
  <T extends string | number | boolean | bigint>(
    key: StorageKey,
    initialValue: T
  ): LocalStorageItemResult<WidenLiteral<T>>;
  <T extends NonNullish>(key: StorageKey, initialValue: T): LocalStorageItemResult<T>;
  <T>(key: StorageKey, initialValue?: T | null): LocalStorageItemResult<T | null>;
};

export const useMyLocalStorageItem: UseMyLocalStorageItem = <T>(key: StorageKey, initialValue?: T | null) => {
  return useLocalStorageItem<T>(`${MY_LOCAL_STORAGE_PREFIX}.${key}`, initialValue);
};

export const useMyLocalStorageProvider = (): LocalStorageContextType => {
  return useContext(LocalStorageContext);
};

export default useMyLocalStorage;
