/// <reference types="vitest" />
import { afterEach, describe, expect, it } from 'vitest';
import { StorageKey } from './constants';
import { getStored, removeStored, saveLoginCredential, setStored } from './localStorage';

const PREFIX = 'howler.ui';

describe('localStorage utilities', () => {
  afterEach(() => {
    localStorage.clear();
  });

  // -------------------------------------------------------------------------
  // setStored / getStored
  // -------------------------------------------------------------------------
  describe('setStored / getStored', () => {
    it('stores and retrieves a string value', () => {
      setStored(StorageKey.USERNAME, 'alice');
      expect(getStored(StorageKey.USERNAME)).toBe('alice');
    });

    it('stores and retrieves an object value', () => {
      const value = { token: 'abc', expires: 123 };
      setStored(StorageKey.APP_TOKEN, value);
      expect(getStored(StorageKey.APP_TOKEN)).toEqual(value);
    });

    it('uses the prefixed key in the underlying localStorage', () => {
      setStored(StorageKey.USERNAME, 'bob');
      expect(localStorage.getItem(`${PREFIX}.${StorageKey.USERNAME}`)).toBe(JSON.stringify('bob'));
    });

    it('returns null for a key that has not been set', () => {
      expect(getStored(StorageKey.USERNAME)).toBeNull();
    });

    it('overwrites an existing value', () => {
      setStored(StorageKey.USERNAME, 'alice');
      setStored(StorageKey.USERNAME, 'bob');
      expect(getStored(StorageKey.USERNAME)).toBe('bob');
    });

    it('stores a number value', () => {
      setStored(StorageKey.PAGE_COUNT, 25);
      expect(getStored(StorageKey.PAGE_COUNT)).toBe(25);
    });
  });

  // -------------------------------------------------------------------------
  // removeStored
  // -------------------------------------------------------------------------
  describe('removeStored', () => {
    it('removes an existing key so it returns null on subsequent reads', () => {
      setStored(StorageKey.USERNAME, 'alice');
      removeStored(StorageKey.USERNAME);
      expect(getStored(StorageKey.USERNAME)).toBeNull();
    });

    it('does not throw when removing a key that was never stored', () => {
      expect(() => removeStored(StorageKey.USERNAME)).not.toThrow();
    });

    it('removes only the targeted key and leaves others intact', () => {
      setStored(StorageKey.USERNAME, 'alice');
      setStored(StorageKey.PROVIDER, 'howler');
      removeStored(StorageKey.USERNAME);
      expect(getStored(StorageKey.USERNAME)).toBeNull();
      expect(getStored(StorageKey.PROVIDER)).toBe('howler');
    });
  });

  // -------------------------------------------------------------------------
  // saveLoginCredential
  // -------------------------------------------------------------------------
  describe('saveLoginCredential', () => {
    it('returns true and stores app_token when app_token is present', () => {
      const result = saveLoginCredential({ app_token: 'tok123' });
      expect(result).toBe(true);
      expect(getStored(StorageKey.APP_TOKEN)).toBe('tok123');
    });

    it('also stores refresh_token and provider when they are present', () => {
      saveLoginCredential({ app_token: 'tok', refresh_token: 'ref', provider: 'howler' });
      expect(getStored(StorageKey.REFRESH_TOKEN)).toBe('ref');
      expect(getStored(StorageKey.PROVIDER)).toBe('howler');
    });

    it('does not store refresh_token when it is absent', () => {
      saveLoginCredential({ app_token: 'tok' });
      expect(getStored(StorageKey.REFRESH_TOKEN)).toBeNull();
    });

    it('returns false and clears stored tokens when app_token is absent', () => {
      setStored(StorageKey.APP_TOKEN, 'old-token');
      setStored(StorageKey.REFRESH_TOKEN, 'old-refresh');
      const result = saveLoginCredential({});
      expect(result).toBe(false);
      expect(getStored(StorageKey.APP_TOKEN)).toBeNull();
      expect(getStored(StorageKey.REFRESH_TOKEN)).toBeNull();
    });

    it('clears APP_TOKEN, REFRESH_TOKEN, and PROVIDER on empty credential', () => {
      setStored(StorageKey.APP_TOKEN, 't');
      setStored(StorageKey.REFRESH_TOKEN, 'r');
      setStored(StorageKey.PROVIDER, 'p');
      saveLoginCredential({});
      expect(getStored(StorageKey.APP_TOKEN)).toBeNull();
      expect(getStored(StorageKey.REFRESH_TOKEN)).toBeNull();
      expect(getStored(StorageKey.PROVIDER)).toBeNull();
    });
  });
});
