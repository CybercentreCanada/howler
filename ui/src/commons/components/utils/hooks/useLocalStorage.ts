import { useCallback, useMemo } from 'react';

export default function useLocalStorage(prefix?: string) {
  // Build the name of the key.
  // If a 'prefix' was specified, the 'key' will be appended to the 'prefix' automatically.
  const _buildKey = useCallback((name: string): string => (prefix ? `${prefix}.${name}` : name), [prefix]);

  // Get an item from local storage.
  // If a 'prefix' was specified, the 'key' will be appended to the 'prefix' automatically.
  const get = useCallback(
    <T>(key: string): T => {
      try {
        return JSON.parse(localStorage.getItem(_buildKey(key)));
      } catch (e) {
        return null;
      }
    },
    [_buildKey]
  );

  // Set an item to local storage.
  // If a 'prefix' was specified, the 'key' will be appended to the 'prefix' automatically.
  const set = useCallback(
    (key: string, value: any) => localStorage.setItem(_buildKey(key), JSON.stringify(value)),
    [_buildKey]
  );

  // Remove an item from local storage.
  // If a 'prefix' was specified, the 'key' will be appended to the 'prefix' automatically.
  const remove = useCallback(
    (key: string, withPrefix: boolean = false) => localStorage.removeItem(withPrefix ? key : _buildKey(key)),
    [_buildKey]
  );

  // Indicates if the local storage has an item with the specified key.
  // If a 'prefix' was specified, the 'key' will be appended to the 'prefix' automatically.
  const has = useCallback((key: string) => get(key) !== null, [get]);

  // Get all the keys in the local storage.
  const keys = useCallback(() => Object.keys(localStorage), []);

  // Get the local storage items {key: string, value: any}.
  // If a 'prefix' key was specified, it will return the items that have a key starting with the prefix.
  // If no 'prefix' was specified, it will return all items.
  const items = useCallback(() => keys().map(k => ({ key: k, value: get(k) })), [get, keys]);

  // Clear all local storage.
  // If a 'prefix' key was specified, it will only clear/remove the items that start with that key.
  // If no 'prefix' key was specified, it will clear/remove all of them.
  const clear = useCallback(
    () =>
      keys().forEach(key => {
        if (prefix && key.startsWith(prefix)) {
          remove(key, true);
        } else if (!prefix) {
          remove(key);
        }
      }),
    [prefix, remove, keys]
  );

  // Return memoized object to prevent unecessary renders.
  return useMemo(
    () => ({
      get,
      set,
      remove,
      has,
      keys,
      items,
      clear
    }),
    [get, set, remove, has, keys, items, clear]
  );
}
