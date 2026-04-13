/// <reference types="vitest" />
import { act, renderHook } from '@testing-library/react';
import { createElement, type FC, type PropsWithChildren } from 'react';
import { MemoryRouter, useSearchParams } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import useParamState from './useParamState';

// Creates a MemoryRouter wrapper using createElement to avoid JSX in a .ts file
const makeWrapper = (search = ''): FC<PropsWithChildren> => {
  // eslint-disable-next-line react/function-component-definition
  return ({ children }) => createElement(MemoryRouter, { initialEntries: [search ? `/?${search}` : '/'] }, children);
};

// Composite hook: exposes the param state AND the live URL params for URL-level assertions
const useParamStateWithUrl = <T extends string | number | boolean | null>(key: string, defaultValue: T) => {
  const [value, setValue] = useParamState(key, defaultValue);
  const [params] = useSearchParams();
  return { value, setValue, params };
};

describe('useParamState', () => {
  describe('scalar mode – initialization', () => {
    it('returns the default value when the param is absent from the URL', () => {
      const { result } = renderHook(() => useParamState<string>('tab', 'dashboard'), { wrapper: makeWrapper() });
      expect(result.current[0]).toBe('dashboard');
    });

    it('returns null when no default is provided and the param is absent', () => {
      const { result } = renderHook(() => useParamState('tab'), { wrapper: makeWrapper() });
      expect(result.current[0]).toBeNull();
    });

    it('reads a string value present in the URL', () => {
      const { result } = renderHook(() => useParamState<string>('tab', 'dashboard'), {
        wrapper: makeWrapper('tab=settings')
      });
      expect(result.current[0]).toBe('settings');
    });

    it('coerces a URL string to a number when defaultValue is a number', () => {
      const { result } = renderHook(() => useParamState<number>('page', 0), { wrapper: makeWrapper('page=3') });
      expect(result.current[0]).toBe(3);
    });

    it('returns the default number when the URL value is non-numeric', () => {
      const { result } = renderHook(() => useParamState<number>('page', 0), {
        wrapper: makeWrapper('page=notanumber')
      });
      expect(result.current[0]).toBe(0);
    });

    it("coerces 'true' string to boolean true when defaultValue is boolean", () => {
      const { result } = renderHook(() => useParamState<boolean>('active', false), {
        wrapper: makeWrapper('active=true')
      });
      expect(result.current[0]).toBe(true);
    });

    it("coerces 'false' string to boolean false when defaultValue is boolean", () => {
      const { result } = renderHook(() => useParamState<boolean>('active', true), {
        wrapper: makeWrapper('active=false')
      });
      expect(result.current[0]).toBe(false);
    });
  });

  describe('scalar mode – setter', () => {
    it('updates the in-state value', () => {
      const { result } = renderHook(() => useParamState<string>('tab', 'dashboard'), { wrapper: makeWrapper() });
      act(() => result.current[1]('settings'));
      expect(result.current[0]).toBe('settings');
    });

    it('writes the new value to the URL', () => {
      const { result } = renderHook(() => useParamStateWithUrl<string>('tab', 'dashboard'), { wrapper: makeWrapper() });
      act(() => result.current.setValue('settings'));
      expect(result.current.params.get('tab')).toBe('settings');
    });

    it('removes the param from the URL when set to the default value', () => {
      const { result } = renderHook(() => useParamStateWithUrl<string>('tab', 'dashboard'), {
        wrapper: makeWrapper('tab=settings')
      });
      act(() => result.current.setValue('dashboard'));
      expect(result.current.params.has('tab')).toBe(false);
    });

    it('removes the param from the URL when set to null', () => {
      const { result } = renderHook(() => useParamStateWithUrl('tab', null), {
        wrapper: makeWrapper('tab=settings')
      });
      act(() => result.current.setValue(null));
      expect(result.current.params.has('tab')).toBe(false);
    });

    it('serializes a number to the URL', () => {
      const { result } = renderHook(() => useParamStateWithUrl<number>('page', 0), { wrapper: makeWrapper() });
      act(() => result.current.setValue(5));
      expect(result.current.params.get('page')).toBe('5');
    });

    it('removes the param when a number is set back to its default', () => {
      const { result } = renderHook(() => useParamStateWithUrl<number>('page', 0), { wrapper: makeWrapper('page=3') });
      act(() => result.current.setValue(0));
      expect(result.current.params.has('page')).toBe(false);
    });

    it('serializes boolean true to the URL', () => {
      const { result } = renderHook(() => useParamStateWithUrl<boolean>('active', false), { wrapper: makeWrapper() });
      act(() => result.current.setValue(true));
      expect(result.current.params.get('active')).toBe('true');
    });

    it('removes boolean param when set back to its default', () => {
      const { result } = renderHook(() => useParamStateWithUrl<boolean>('active', false), {
        wrapper: makeWrapper('active=true')
      });
      act(() => result.current.setValue(false));
      expect(result.current.params.has('active')).toBe(false);
    });

    it('does not clobber unrelated URL params when writing', () => {
      const { result } = renderHook(() => useParamStateWithUrl<string>('tab', 'dashboard'), {
        wrapper: makeWrapper('sort=asc')
      });
      act(() => result.current.setValue('settings'));
      expect(result.current.params.get('sort')).toBe('asc');
    });
  });

  describe('list mode – initialization', () => {
    it('returns an empty array when no list params are present', () => {
      const { result } = renderHook(() => useParamState<string>('tag', 'x', true), { wrapper: makeWrapper() });
      expect(result.current[0]).toEqual([]);
    });

    it('reads multiple values from the URL', () => {
      const { result } = renderHook(() => useParamState<string>('tag', 'x', true), {
        wrapper: makeWrapper('tag=a&tag=b&tag=c')
      });
      expect(result.current[0]).toEqual(['a', 'b', 'c']);
    });
  });

  describe('list mode – setter', () => {
    it('updates the in-state array value', () => {
      const { result } = renderHook(() => useParamState<string>('tag', '', true), { wrapper: makeWrapper() });
      act(() => result.current[1](['alpha', 'beta']));
      expect(result.current[0]).toEqual(['alpha', 'beta']);
    });

    it('writes multiple values as repeated URL params', () => {
      const { result } = renderHook(
        () => {
          const [value, setValue] = useParamState<string>('tag', '', true);
          const [params] = useSearchParams();
          return { value, setValue, params };
        },
        { wrapper: makeWrapper() }
      );
      act(() => result.current.setValue(['x', 'y', 'z']));
      expect(result.current.params.getAll('tag')).toEqual(['x', 'y', 'z']);
    });

    it('clears all repeated params when set to an empty array', () => {
      const { result } = renderHook(
        () => {
          const [value, setValue] = useParamState<string>('tag', '', true);
          const [params] = useSearchParams();
          return { value, setValue, params };
        },
        { wrapper: makeWrapper('tag=a&tag=b') }
      );
      act(() => result.current.setValue([]));
      expect(result.current.params.getAll('tag')).toEqual([]);
    });

    it('replaces existing params entirely on update', () => {
      const { result } = renderHook(
        () => {
          const [value, setValue] = useParamState<string>('tag', '', true);
          const [params] = useSearchParams();
          return { value, setValue, params };
        },
        { wrapper: makeWrapper('tag=old1&tag=old2') }
      );
      act(() => result.current.setValue(['new1']));
      expect(result.current.params.getAll('tag')).toEqual(['new1']);
    });

    it('does not clobber unrelated URL params when writing list values', () => {
      const { result } = renderHook(
        () => {
          const [value, setValue] = useParamState<string>('tag', '', true);
          const [params] = useSearchParams();
          return { value, setValue, params };
        },
        { wrapper: makeWrapper('sort=asc') }
      );
      act(() => result.current.setValue(['x']));
      expect(result.current.params.get('sort')).toBe('asc');
    });
  });
});
