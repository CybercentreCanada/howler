import type { LoginResponse } from 'api/auth/login';
import { MY_LOCAL_STORAGE_PREFIX, StorageKey } from './constants';

const buildName = (name: string) => `${MY_LOCAL_STORAGE_PREFIX}.${name}`;

/**
 * **IMPORTANT**: This function should only be used OUTSIDE of the React tree.
 * If you want to edit localStorage items inside a React component, use
 * src/components/hooks/useMyLocalStorage.tsx.
 */
export const removeStored = (name: StorageKey) => {
  localStorage.removeItem(buildName(name));
};

/**
 * **IMPORTANT**: This function should only be used OUTSIDE of the React tree.
 * If you want to edit localStorage items inside a React component, use
 * src/components/hooks/useMyLocalStorage.tsx.
 */
export const setStored = (name: StorageKey, item: any) => {
  localStorage.setItem(buildName(name), JSON.stringify(item));
};

/**
 * **IMPORTANT**: This function should only be used OUTSIDE of the React tree.
 * If you want to edit localStorage items inside a React component, use
 * src/components/hooks/useMyLocalStorage.tsx.
 */
export const getStored = <T = string>(name?: StorageKey): T => {
  try {
    return JSON.parse(localStorage.getItem(buildName(name))) as T;
  } catch (e) {
    // Migrating from the old system, some values were not JSON encoded. Decoding them will cause an exception.
    // Obviously, this is not optimal, but it's the only way to get Typescript to play nice.
    // When this is called, T will be type string.
    return localStorage.getItem(buildName(name)) as unknown as T;
  }
};

export const saveLoginCredential = (loginRes: LoginResponse) => {
  if (loginRes.app_token) {
    setStored(StorageKey.APP_TOKEN, loginRes.app_token);
    if (loginRes.refresh_token) {
      setStored(StorageKey.REFRESH_TOKEN, loginRes.refresh_token);
      setStored(StorageKey.PROVIDER, loginRes.provider);
    }
    return true;
  }

  removeStored(StorageKey.REFRESH_TOKEN);
  removeStored(StorageKey.APP_TOKEN);
  removeStored(StorageKey.PROVIDER);
  return false;
};
