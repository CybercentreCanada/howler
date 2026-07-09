import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { StorageKey } from './constants';
import { getAxiosCache, getStored, removeStored, setAxiosCache, setStored } from './sessionStorage';

// The sessionStorage module uses a debounced write (3 000 ms). Tests that need to verify
// persistence to sessionStorage use fake timers and advance past the debounce delay.
// afterEach flushes any pending changes so module-level state is clean for the next test.

const DEBOUNCE_MS = 3100; // slightly past the 3 000 ms throttle
const SESSION_PREFIX = 'howler.ui.cache';

describe('sessionStorage utilities', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    // Flush pending debounced writes – this also resets the internal `changes` map.
    vi.advanceTimersByTime(DEBOUNCE_MS);
    vi.useRealTimers();
    sessionStorage.clear();
  });

  // -------------------------------------------------------------------------
  // getAxiosCache / setAxiosCache
  // -------------------------------------------------------------------------
  describe('getAxiosCache / setAxiosCache', () => {
    it('returns an empty object when no cache has been stored', () => {
      expect(getAxiosCache()).toEqual({});
    });

    it('stores and retrieves a cached entry after the debounce fires', () => {
      setAxiosCache('etag-1', { data: 'value' });
      vi.advanceTimersByTime(DEBOUNCE_MS);
      expect(getAxiosCache()['etag-1']).toEqual({ data: 'value' });
    });

    it('accumulates multiple distinct cache entries', () => {
      setAxiosCache('etag-a', { data: 'a' });
      setAxiosCache('etag-b', { data: 'b' });
      vi.advanceTimersByTime(DEBOUNCE_MS);
      const cache = getAxiosCache();
      expect(cache['etag-a']).toEqual({ data: 'a' });
      expect(cache['etag-b']).toEqual({ data: 'b' });
    });

    it('overwrites an earlier entry for the same etag', () => {
      setAxiosCache('etag-1', { data: 'old' });
      setAxiosCache('etag-1', { data: 'new' });
      vi.advanceTimersByTime(DEBOUNCE_MS);
      expect(getAxiosCache()['etag-1']).toEqual({ data: 'new' });
    });
  });

  // -------------------------------------------------------------------------
  // setStored / getStored (object values)
  // -------------------------------------------------------------------------
  describe('setStored / getStored', () => {
    it('makes an object value immediately readable via getStored (in-memory, before flush)', () => {
      setStored(StorageKey.AXIOS_CACHE, { immediate: true });
      // Timer has NOT advanced yet – data is in the in-memory `changes` map.
      const result = getStored<{ immediate: boolean }>(StorageKey.AXIOS_CACHE);
      expect(result.immediate).toBe(true);
    });

    it('persists an object value to sessionStorage after the debounce delay', () => {
      const key = `${SESSION_PREFIX}.${StorageKey.AXIOS_CACHE}`;
      setStored(StorageKey.AXIOS_CACHE, { persisted: true });
      // Before flush: sessionStorage is still empty.
      expect(sessionStorage.getItem(key)).toBeNull();
      vi.advanceTimersByTime(DEBOUNCE_MS);
      expect(JSON.parse(sessionStorage.getItem(key))).toEqual({ persisted: true });
    });
  });

  // -------------------------------------------------------------------------
  // removeStored
  // -------------------------------------------------------------------------
  describe('removeStored', () => {
    it('removes a key from sessionStorage', () => {
      setStored(StorageKey.AXIOS_CACHE, { val: 1 });
      vi.advanceTimersByTime(DEBOUNCE_MS);
      removeStored(StorageKey.AXIOS_CACHE);
      const key = `${SESSION_PREFIX}.${StorageKey.AXIOS_CACHE}`;
      expect(sessionStorage.getItem(key)).toBeNull();
    });

    it('does not throw when removing a key that was never set', () => {
      expect(() => removeStored(StorageKey.AXIOS_CACHE)).not.toThrow();
    });
  });
});
