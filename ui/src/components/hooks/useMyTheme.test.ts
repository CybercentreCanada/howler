/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import useMyTheme from './useMyTheme';

describe('useMyTheme', () => {
  it('returns a theme configuration object', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current).toBeDefined();
    expect(typeof result.current).toBe('object');
  });

  it('contains a dark palette entry', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.palette?.dark).toBeDefined();
  });

  it('contains a light palette entry', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.palette?.light).toBeDefined();
  });

  it('returns the same reference on re-render (stable return value)', () => {
    const { result, rerender } = renderHook(() => useMyTheme());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });

  it('dark palette includes primary and secondary colours', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.palette.dark.primary?.main).toBeTruthy();
    expect(result.current.palette.dark.secondary?.main).toBeTruthy();
  });

  it('light palette includes primary and secondary colours', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.palette.light.primary?.main).toBeTruthy();
    expect(result.current.palette.light.secondary?.main).toBeTruthy();
  });
});
