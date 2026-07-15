import Throttler from 'utils/Throttler';
import { MY_SESSION_STORAGE_PREFIX, StorageKey } from './constants';

const buildName = (name: string) => `${MY_SESSION_STORAGE_PREFIX}.${name}`;

const {
  _getStored: getStored,
  _removeStored: removeStored,
  _setStored: setStored
} = (() => {
  // In order to tamp down on the number of writes to session storage, we use a throttler to debounce writes.
  // This allows us to write to the same key many times in quick succession without actually writing it to session storage right away.
  const throttler = new Throttler(3000);

  let changes = {};

  const _getStored = <T = string>(name: StorageKey): T => {
    return {
      ...JSON.parse(sessionStorage.getItem(buildName(name))),
      ...changes[buildName(name)]
    } as T;
  };

  const _removeStored = (name: StorageKey) => {
    delete changes[buildName(name)];
    sessionStorage.removeItem(buildName(name));
  };

  const _setStored = (name: StorageKey, item: any) => {
    changes[buildName(name)] = item;

    throttler.debounce(() => {
      Object.entries(changes).forEach(([_name, data]) => {
        try {
          sessionStorage.setItem(_name, JSON.stringify(data));
        } catch (e) {
          // eslint-disable-next-line no-console
          console.warn('Quota Error when saving to sessionStorage', e);
        }
      });

      changes = {};
    });
  };

  return { _getStored, _removeStored, _setStored };
})();

export { getStored, removeStored, setStored };

export const getAxiosCache = (): { [index: string]: any } => {
  return getStored(StorageKey.AXIOS_CACHE) ?? {};
};

export const setAxiosCache = (etag: string, value: any) => {
  const cache = getAxiosCache();
  cache[etag] = value;
  setStored(StorageKey.AXIOS_CACHE, cache);
};
