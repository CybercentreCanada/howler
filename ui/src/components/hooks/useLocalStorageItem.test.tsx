/* eslint-disable @typescript-eslint/no-unused-vars */
/// <reference types="vitest" />
import { act, renderHook } from '@testing-library/react';
import { setupLocalStorageMock } from 'tests/mocks';
import { vi } from 'vitest';
import useLocalStorageItem from './useLocalStorageItem';

const mockLocalStorage = setupLocalStorageMock();

beforeEach(() => {
  mockLocalStorage.clear();
  vi.mocked(mockLocalStorage.setItem).mockClear();
  vi.mocked(mockLocalStorage.removeItem).mockClear();
});

describe('useLocalStorageItem', () => {
  describe('initialization', () => {
    it('returns the initialValue when the key is absent from storage', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 42));
      expect(result.current[0]).toBe(42);
    });

    it('returns the persisted storage value instead of initialValue', () => {
      mockLocalStorage.setItem('testkey', JSON.stringify(99));
      const { result } = renderHook(() => useLocalStorageItem('testkey', 42));
      expect(result.current[0]).toBe(99);
    });

    it('writes initialValue to storage when the key is absent', () => {
      renderHook(() => useLocalStorageItem('testkey', 'hello'));
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('testkey', JSON.stringify('hello'));
    });

    it('does not overwrite an existing storage value with initialValue', () => {
      mockLocalStorage.setItem('testkey', JSON.stringify('existing'));
      vi.mocked(mockLocalStorage.setItem).mockClear();
      renderHook(() => useLocalStorageItem('testkey', 'initial'));
      expect(mockLocalStorage.setItem).not.toHaveBeenCalled();
    });
  });

  describe('setter', () => {
    it('updates the returned value', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 0));
      act(() => result.current[1](7));
      expect(result.current[0]).toBe(7);
    });

    it('persists the new value to localStorage', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 0));
      act(() => result.current[1](7));
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('testkey', JSON.stringify(7));
    });

    it('removes the key from storage when called with undefined', () => {
      const { result } = renderHook(() => useLocalStorageItem<number | undefined>('testkey', 0));
      act(() => result.current[1](undefined));
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('testkey');
    });

    it('skips persisting to storage when save=false', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 0));
      vi.mocked(mockLocalStorage.setItem).mockClear();
      act(() => (result.current[1] as any)(10, false));
      expect(result.current[0]).toBe(10);
      expect(mockLocalStorage.setItem).not.toHaveBeenCalled();
    });
  });

  describe('reset function', () => {
    it('removes the key from localStorage', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 0));
      act(() => result.current[1](5));
      act(() => result.current[2]());
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('testkey');
    });

    it('resets the value back to initialValue', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 0));
      act(() => result.current[1](5));
      act(() => result.current[2]());
      expect(result.current[0]).toBe(0);
    });
  });

  describe('cross-component synchronization (same tab)', () => {
    it('propagates updates to all hooks sharing the same key', () => {
      const { result: a } = renderHook(() => useLocalStorageItem('shared', 0));
      const { result: b } = renderHook(() => useLocalStorageItem('shared', 0));

      act(() => a.current[1](42));

      expect(a.current[0]).toBe(42);
      expect(b.current[0]).toBe(42);
    });

    it('does not affect hooks using a different key', () => {
      const { result: a } = renderHook(() => useLocalStorageItem('key-a', 0));
      const { result: b } = renderHook(() => useLocalStorageItem('key-b', 0));

      act(() => a.current[1](99));

      expect(b.current[0]).toBe(0);
    });

    it('propagates the reset to all hooks sharing the same key', () => {
      const { result: a } = renderHook(() => useLocalStorageItem('shared', 0));
      const { result: b } = renderHook(() => useLocalStorageItem('shared', 0));

      act(() => a.current[1](5));
      act(() => a.current[2]());

      expect(a.current[0]).toBe(0);
      expect(b.current[0]).toBe(0);
    });

    it('propagates save=false updates to other subscribers', () => {
      const { result: a } = renderHook(() => useLocalStorageItem('testkey', 0));
      const { result: b } = renderHook(() => useLocalStorageItem('testkey', 0));

      act(() => (a.current[1] as any)(10, false));

      expect(b.current[0]).toBe(10);
    });

    it('stops receiving updates after unmount', () => {
      const { result: a, unmount } = renderHook(() => useLocalStorageItem('shared', 0));
      const { result: b } = renderHook(() => useLocalStorageItem('shared', 0));

      unmount();
      act(() => b.current[1](55));

      // b must have the new value; a is unmounted so no further updates reach it
      expect(a.current[0]).toBe(0);
      expect(b.current[0]).toBe(55);
    });
  });

  describe('cross-tab synchronization (storage event)', () => {
    it('reacts to a storage event for the same key', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 0));

      act(() => {
        window.dispatchEvent(new StorageEvent('storage', { key: 'testkey', newValue: JSON.stringify(77) }));
      });

      expect(result.current[0]).toBe(77);
    });

    it('ignores storage events for different keys', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 0));

      act(() => {
        window.dispatchEvent(new StorageEvent('storage', { key: 'other-key', newValue: JSON.stringify(99) }));
      });

      expect(result.current[0]).toBe(0);
    });

    it('falls back to initialValue when a storage event clears the key (newValue=null)', () => {
      const { result } = renderHook(() => useLocalStorageItem('testkey', 5));

      act(() => result.current[1](20));
      act(() => {
        window.dispatchEvent(new StorageEvent('storage', { key: 'testkey', newValue: null }));
      });

      expect(result.current[0]).toBe(5);
    });

    it('propagates cross-tab updates to all same-tab subscribers', () => {
      const { result: a } = renderHook(() => useLocalStorageItem('testkey', 0));
      const { result: b } = renderHook(() => useLocalStorageItem('testkey', 0));

      act(() => {
        window.dispatchEvent(new StorageEvent('storage', { key: 'testkey', newValue: JSON.stringify(33) }));
      });

      expect(a.current[0]).toBe(33);
      expect(b.current[0]).toBe(33);
    });
  });
});
