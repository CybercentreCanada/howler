/// <reference types="vitest" />
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockAddRecordToSelection = vi.hoisted(() => vi.fn());
const mockRemoveRecordFromSelection = vi.hoisted(() => vi.fn());
const mockClearSelectedRecords = vi.hoisted(() => vi.fn());
const mockSetSelected = vi.hoisted(() => vi.fn());
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));

let selectedRecords: any[] = [];
let responseItems: any[] = [];

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('use-context-selector', async importOriginal => {
  const actual = await importOriginal<typeof import('use-context-selector')>();
  return {
    ...actual,
    useContextSelector: (context: any, selector: (ctx: any) => any) => {
      if (context === recordSearchContextToken) {
        return selector({ response: { items: responseItems } });
      }
      if (context === recordContextToken) {
        return selector({
          selectedRecords,
          addRecordToSelection: mockAddRecordToSelection,
          removeRecordFromSelection: mockRemoveRecordFromSelection,
          clearSelectedRecords: mockClearSelectedRecords
        });
      }
      if (context === parameterContextToken) {
        return selector({ setSelected: mockSetSelected });
      }
      return selector(null);
    }
  };
});

import useRecordSelection from './useRecordSelection';

describe('useRecordSelection', () => {
  beforeEach(() => {
    selectedRecords = [];
    responseItems = [{ howler: { id: 'a' } }, { howler: { id: 'b' } }, { howler: { id: 'c' } }];
    mockAddRecordToSelection.mockReset();
    mockRemoveRecordFromSelection.mockReset();
    mockClearSelectedRecords.mockReset();
    mockSetSelected.mockReset();
    document.getSelection = vi.fn(() => ({ removeAllRanges: vi.fn() } as any));
  });

  it('selects a single record on normal click', () => {
    const { result } = renderHook(() => useRecordSelection());
    const event = { ctrlKey: false, shiftKey: false } as any;

    act(() => {
      result.current.onClick(event, { howler: { id: 'b' } } as any);
    });

    expect(result.current.lastSelected).toBe('b');
    expect(mockClearSelectedRecords).toHaveBeenCalledWith('b');
    expect(mockSetSelected).toHaveBeenCalledWith('b');
  });

  it('toggles ctrl-clicked records in the multi-selection set', () => {
    selectedRecords = [{ howler: { id: 'b' } }];
    const { result } = renderHook(() => useRecordSelection());
    const stopPropagation = vi.fn();

    act(() => {
      result.current.onClick({ ctrlKey: true, shiftKey: false, stopPropagation } as any, { howler: { id: 'b' } } as any);
    });
    expect(mockRemoveRecordFromSelection).toHaveBeenCalledWith('b');

    selectedRecords = [];
    act(() => {
      result.current.onClick({ ctrlKey: true, shiftKey: false, stopPropagation } as any, { howler: { id: 'c' } } as any);
    });
    expect(mockAddRecordToSelection).toHaveBeenCalledWith('c');
    expect(stopPropagation).toHaveBeenCalledTimes(2);
  });

  it('adds a shift-click range from the last selected hit', () => {
    selectedRecords = [{ howler: { id: 'a' } }];
    const { result, rerender } = renderHook(() => useRecordSelection());
    act(() => {
      result.current.setLastSelected('a');
    });
    rerender();

    act(() => {
      result.current.onClick({ ctrlKey: false, shiftKey: true, stopPropagation: vi.fn() } as any, { howler: { id: 'c' } } as any);
    });

    expect(mockAddRecordToSelection).toHaveBeenCalledWith('a');
    expect(mockAddRecordToSelection).toHaveBeenCalledWith('b');
    expect(mockAddRecordToSelection).toHaveBeenCalledWith('c');
  });

  it('handles shift-click when nothing is selected yet', () => {
    const { result } = renderHook(() => useRecordSelection());

    act(() => {
      result.current.onClick({ ctrlKey: false, shiftKey: true, stopPropagation: vi.fn() } as any, { howler: { id: 'a' } } as any);
    });

    expect(mockAddRecordToSelection).toHaveBeenCalledWith('a');
  });
});
