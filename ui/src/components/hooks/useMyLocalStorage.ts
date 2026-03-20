import { LocalStorageContext, type LocalStorageContextType } from 'components/app/providers/LocalStorageProvider';
import { useContext } from 'react';
import type { StorageKey } from 'utils/constants';
import { MY_LOCAL_STORAGE_PREFIX } from 'utils/constants';
import useLocalStorage from './useLocalStorage';
import useLocalStorageItem from './useLocalStorageItem';

const useMyLocalStorage = () => {
  return useLocalStorage(MY_LOCAL_STORAGE_PREFIX);
};

export const useMyLocalStorageItem = <T>(key: StorageKey, initialValue?: T) => {
  return useLocalStorageItem(`${MY_LOCAL_STORAGE_PREFIX}.${key}`, initialValue);
};

export const useMyLocalStorageProvider = (): LocalStorageContextType => {
  return useContext(LocalStorageContext);
};

export default useMyLocalStorage;
