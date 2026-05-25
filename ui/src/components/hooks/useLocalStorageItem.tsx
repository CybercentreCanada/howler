import useLocalStorage from 'components/hooks/useLocalStorage';
import { useEffect, useMemo, useState } from 'react';

// Module-level subscriber map for same-page cross-component synchronization.
// Maps each storage key to the set of React state setters currently subscribed to it.
const SUBSCRIBERS = new Map<string, Set<(v: unknown) => void>>();

const notify = (key: string, value: unknown) => {
  SUBSCRIBERS.get(key)?.forEach(setter => setter(value));
};

/**
 * This hooks backs the typical 'useState' hook with local storage.
 *
 * This means that it will initialize with the value stored in local storage.
 *
 * State changes are also persisted to local storage.
 *
 * All callers sharing the same key share a single logical state: updating the
 * value in one component automatically re-renders all others using the same key,
 * both within the same tab (via the module-level subscriber map) and across tabs
 * (via the native 'storage' event).
 *
 * @param key - local storage key under which to store the state.
 * @param initialValue - local storage initialization value.
 * @returns a stateful value, a function to update it, and a function to remove it.
 */
const useLocalStorageItem = <T,>(key: string, initialValue?: T): [T, (value: T) => void, () => void] => {
  const { get, set, has, remove } = useLocalStorage();
  const [value, setValue] = useState<T>(get(key) ?? initialValue);

  useEffect(() => {
    if (initialValue !== null && initialValue !== undefined && !has(key)) {
      set(key, initialValue);
    }
  }, [key, initialValue, has, set]);

  // Register this instance's setter in the subscriber map.
  useEffect(() => {
    if (!SUBSCRIBERS.has(key)) {
      SUBSCRIBERS.set(key, new Set());
    }
    const setter = (v: unknown) => setValue(v as T);
    SUBSCRIBERS.get(key).add(setter);
    return () => {
      SUBSCRIBERS.get(key)?.delete(setter);
      if (SUBSCRIBERS.get(key)?.size === 0) {
        SUBSCRIBERS.delete(key);
      }
    };
  }, [key]);

  // React to cross-tab storage changes via the native 'storage' event.
  useEffect(() => {
    const handler = (event: StorageEvent) => {
      if (event.key !== key) return;
      const next: T = event.newValue !== null ? JSON.parse(event.newValue) : initialValue;
      notify(key, next);
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, [key, initialValue]);

  return useMemo(
    () => [
      value,
      (newValue, save = true) => {
        if (save) {
          if (newValue !== undefined) {
            set(key, newValue);
          } else {
            remove(key);
          }
        }

        // Update all subscribers for this key (including this instance).
        notify(key, newValue);
      },
      () => {
        remove(key);
        notify(key, initialValue);
      }
    ],
    [key, value, initialValue, set, remove]
  );
};

export default useLocalStorageItem;
