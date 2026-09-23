/// <reference types="vitest" />
import { act, renderHook, waitFor } from '@testing-library/react';
import { useContext } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { StorageKey } from 'utils/constants';

const mockGetStored = vi.hoisted(() => vi.fn());
const mockSetStored = vi.hoisted(() => vi.fn());
const mockRemoveStored = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useLocalStorage', () => ({
  default: () => ({
    get: mockGetStored,
    set: mockSetStored,
    remove: mockRemoveStored
  })
}));

import LocalStorageProvider, { LocalStorageContext } from './LocalStorageProvider';

describe('LocalStorageProvider', () => {
  it('hydrates values, updates stored state, and removes keys', async () => {
    mockGetStored.mockImplementation((key: string) => {
      if (key === StorageKey.PAGE_COUNT) return 25;
      if (key === StorageKey.NEXT_LOCATION) return '/hits';
      return undefined;
    });

    const wrapper = ({ children }: any) => <LocalStorageProvider>{children}</LocalStorageProvider>;
    const { result } = renderHook(() => useContext(LocalStorageContext), { wrapper });

    await waitFor(() => expect(result.current.values[StorageKey.PAGE_COUNT]).toBe(25));
    expect(result.current.values[StorageKey.NEXT_LOCATION]).toBe('/hits');

    act(() => {
      result.current.set(StorageKey.PAGE_COUNT, 50);
    });
    expect(mockSetStored).toHaveBeenCalledWith(StorageKey.PAGE_COUNT, 50);
    expect(result.current.values[StorageKey.PAGE_COUNT]).toBe(50);

    act(() => {
      result.current.remove(StorageKey.PAGE_COUNT);
    });
    expect(mockRemoveStored).toHaveBeenCalledWith(StorageKey.PAGE_COUNT);
    expect(result.current.values[StorageKey.PAGE_COUNT]).toBeUndefined();
  });
});
