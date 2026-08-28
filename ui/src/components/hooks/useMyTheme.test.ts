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
    expect(result.current.dark?.palette).toBeDefined();
  });

  it('sets the dark palette mode', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.dark?.palette?.mode).toBe('dark');
  });

  it('contains a light palette entry', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.light?.palette).toBeDefined();
  });

  it('returns the same reference on re-render (stable return value)', () => {
    const { result, rerender } = renderHook(() => useMyTheme());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });

  it('dark palette includes primary and secondary colours', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.dark.palette.primary).toHaveProperty('main');
    expect(result.current.dark.palette.secondary).toHaveProperty('main');
  });

  it('light palette includes primary and secondary colours', () => {
    const { result } = renderHook(() => useMyTheme());
    expect(result.current.light.palette.primary).toHaveProperty('main');
    expect(result.current.light.palette.secondary).toHaveProperty('main');
  });
});
