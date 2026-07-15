/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { setupLocalStorageMock } from 'tests/mocks';
import { describe, expect, it, vi } from 'vitest';
import useLocalStorage from './useLocalStorage';

const mockLocalStorage = setupLocalStorageMock();

beforeEach(() => {
  mockLocalStorage.clear();
  vi.mocked(mockLocalStorage.setItem).mockClear();
  vi.mocked(mockLocalStorage.removeItem).mockClear();
});

describe('useLocalStorage (no prefix)', () => {
  describe('get', () => {
    it('returns null when key is absent', () => {
      const { result } = renderHook(() => useLocalStorage());
      expect(result.current.get('testkey')).toBeNull();
    });

    it('returns the parsed value when key exists', () => {
      mockLocalStorage.setItem('testkey', JSON.stringify(42));
      const { result } = renderHook(() => useLocalStorage());
      expect(result.current.get('testkey')).toBe(42);
    });

    it('returns null when the raw value is not valid JSON', () => {
      mockLocalStorage.setItem('testkey', 'not-json{');
      const { result } = renderHook(() => useLocalStorage());
      expect(result.current.get('testkey')).toBeNull();
    });
  });

  describe('set', () => {
    it('serializes and writes a value', () => {
      const { result } = renderHook(() => useLocalStorage());
      result.current.set('testkey', { a: 1 });
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('testkey', JSON.stringify({ a: 1 }));
    });

    it('written value can be read back', () => {
      const { result } = renderHook(() => useLocalStorage());
      result.current.set('testkey', 'hello');
      expect(result.current.get('testkey')).toBe('hello');
    });
  });

  describe('remove', () => {
    it('removes the key', () => {
      const { result } = renderHook(() => useLocalStorage());
      result.current.set('testkey', 'val');
      result.current.remove('testkey');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('testkey');
      expect(result.current.has('testkey')).toBe(false);
    });

    it('removes with a raw key when withPrefix=true', () => {
      const { result } = renderHook(() => useLocalStorage('myprefix'));
      result.current.remove('raw.key', true);
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('raw.key');
    });
  });

  describe('has', () => {
    it('returns false when key is absent', () => {
      const { result } = renderHook(() => useLocalStorage());
      expect(result.current.has('testkey')).toBe(false);
    });

    it('returns true when key exists', () => {
      const { result } = renderHook(() => useLocalStorage());
      result.current.set('testkey', 0);
      expect(result.current.has('testkey')).toBe(true);
    });
  });

  describe('keys', () => {
    it('returns an empty array when storage is empty', () => {
      const { result } = renderHook(() => useLocalStorage());
      expect(result.current.keys()).toEqual([]);
    });

    it('returns all stored keys', () => {
      const { result } = renderHook(() => useLocalStorage());
      result.current.set('a', 1);
      result.current.set('b', 2);
      expect(result.current.keys()).toEqual(expect.arrayContaining(['a', 'b']));
    });
  });

  describe('items', () => {
    it('returns key-value pairs for all stored items', () => {
      const { result } = renderHook(() => useLocalStorage());
      result.current.set('x', 10);
      result.current.set('y', 20);
      const items = result.current.items();
      expect(items).toEqual(
        expect.arrayContaining([
          { key: 'x', value: 10 },
          { key: 'y', value: 20 }
        ])
      );
    });
  });

  describe('clear', () => {
    it('removes all keys when no prefix is set', () => {
      const { result } = renderHook(() => useLocalStorage());
      result.current.set('a', 1);
      result.current.set('b', 2);
      result.current.clear();
      expect(result.current.keys()).toEqual([]);
    });
  });
});

describe('useLocalStorage (with prefix)', () => {
  const PREFIX = 'ns';

  describe('get / set', () => {
    it('writes the key under the prefix', () => {
      const { result } = renderHook(() => useLocalStorage(PREFIX));
      result.current.set('item', 'val');
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('ns.item', JSON.stringify('val'));
    });

    it('reads the key under the prefix', () => {
      mockLocalStorage.setItem('ns.item', JSON.stringify('val'));
      const { result } = renderHook(() => useLocalStorage(PREFIX));
      expect(result.current.get('item')).toBe('val');
    });

    it('does not read a key stored without the prefix', () => {
      mockLocalStorage.setItem('item', JSON.stringify('val'));
      const { result } = renderHook(() => useLocalStorage(PREFIX));
      expect(result.current.get('item')).toBeNull();
    });
  });

  describe('remove', () => {
    it('removes the key under the prefix', () => {
      const { result } = renderHook(() => useLocalStorage(PREFIX));
      result.current.remove('item');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('ns.item');
    });
  });

  describe('clear', () => {
    it('only removes keys that start with the prefix', () => {
      const { result } = renderHook(() => useLocalStorage(PREFIX));
      result.current.set('item', 1);
      mockLocalStorage.setItem('other.item', JSON.stringify(2));
      vi.mocked(mockLocalStorage.removeItem).mockClear();

      result.current.clear();

      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('ns.item');
      expect(mockLocalStorage.removeItem).not.toHaveBeenCalledWith('other.item');
    });
  });
});
