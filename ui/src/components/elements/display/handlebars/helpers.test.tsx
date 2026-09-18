/// <reference types="vitest" />
import { render, renderHook, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockExecuteFunction = vi.hoisted(() => vi.fn());

vi.mock('@tui/core', () => ({
  AppListEmpty: () => <div>empty</div>
}));

vi.mock('@mui/material', () => ({
  Paper: ({ children }: any) => <div>{children}</div>,
  Table: ({ children }: any) => <table>{children}</table>,
  TableBody: ({ children }: any) => <tbody>{children}</tbody>,
  TableCell: ({ children }: any) => <td>{children}</td>,
  TableHead: ({ children }: any) => <thead>{children}</thead>,
  TableRow: ({ children }: any) => <tr>{children}</tr>
}));

vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id, layout }: any) => <div>{`${id}:${layout}`}</div>
}));

vi.mock('components/elements/hit/HitLayout', () => ({
  HitLayout: { NORMAL: 'normal' }
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['demo'] }
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('../ActionButton', () => ({
  default: ({ actionId, hitId, ...rest }: any) => <div>{JSON.stringify({ actionId, hitId, rest })}</div>
}));

vi.mock('../json/JSONViewer', () => ({
  default: ({ data }: any) => <div>{JSON.stringify(data)}</div>
}));

import { HowlerHelperError, useHelpers } from './helpers';

describe('handlebars helpers', () => {
  it('returns built-in and plugin helpers while honoring filter options', () => {
    mockExecuteFunction.mockReturnValue([{ keyword: 'plugin_helper', callback: () => 'plugin' }]);

    const { result } = renderHook(() => useHelpers());
    const keywords = result.current.map(entry => entry.keyword);

    expect(keywords).toContain('equals');
    expect(keywords).toContain('plugin_helper');

    const asyncFiltered = renderHook(() => useHelpers({ async: false, components: true }));
    expect(asyncFiltered.result.current.some(entry => entry.keyword === 'fetch')).toBe(false);

    const componentFiltered = renderHook(() => useHelpers({ async: true, components: false }));
    expect(componentFiltered.result.current.some(entry => entry.keyword === 'howler')).toBe(false);
  });

  it('executes logical/string helpers and reports invalid inputs', async () => {
    mockExecuteFunction.mockReturnValue([]);
    const { result } = renderHook(() => useHelpers());
    const helperMap = Object.fromEntries(result.current.map(entry => [entry.keyword, entry]));
    const options = {};

    expect(helperMap.equals.callback?.('1', 1, options)).toBe(true);
    expect(() => helperMap.equals.callback?.(null, 'x', options)).toThrow(HowlerHelperError);
    expect(helperMap.and.callback?.(true, 'ok', options)).toBe('ok');
    expect(helperMap.or.callback?.('', 'fallback', options)).toBe('fallback');
    expect(helperMap.not.callback?.(0, options)).toBe(true);
    expect(String(helperMap.curly.callback?.('name', options))).toBe('{{name}}');
    expect(helperMap.join.callback?.('hello', 'world', { hash: { sep: '-' } })).toBe('hello-world');
    expect(helperMap.upper.callback?.('hello', options)).toBe('HELLO');
    expect(() => helperMap.upper.callback?.(undefined, options)).toThrow('Upper expects a string argument');
    expect(helperMap.lower.callback?.('HELLO', options)).toBe('hello');
    expect(() => helperMap.lower.callback?.(undefined, options)).toThrow('Lower expects a string argument');
    expect(String(helperMap.to_json.callback?.({ id: 1 }, options))).toBe('{"id":1}');
    expect(helperMap.parse_json.callback?.('{"id":1}', options)).toEqual({ id: 1 });
    expect(() => helperMap.parse_json.callback?.(undefined, options)).toThrow('Parse JSON expects a string argument');
    expect(() => helperMap.parse_json.callback?.('{oops}', options)).toThrow('Invalid JSON string');
    expect(helperMap.get.callback?.({ nested: { value: 7 } }, 'nested.value', options)).toBe(7);
    expect(helperMap.includes.callback?.('abcdef', 'cd', options)).toBe(true);
    expect(helperMap.entries.callback?.({ a: 1 }, options)).toEqual([{ key: 'a', value: 1 }]);
    expect(String(helperMap.entries.callback?.(null, options))).toBe('Invalid Object.');
    expect(helperMap.replace.callback?.('alpha beta', 'beta', 'gamma', options)).toBe('alpha gamma');
    expect(() => helperMap.replace.callback?.('alpha', undefined, 'x', options)).toThrow('Replace expects three arguments');

    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ nested: { value: 'cached' } })
      } as Response)
    ) as any;

    await expect(helperMap.fetch.callback?.('https://example.com/data', 'nested.value', options)).resolves.toBe('cached');
    await expect(helperMap.fetch.callback?.('https://example.com/data', 'nested.value', options)).resolves.toBe('cached');
    await expect(helperMap.fetch.callback?.('https://example.com/data', 'missing.value', options)).resolves.toBeUndefined();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('renders component-backed helpers', () => {
    mockExecuteFunction.mockReturnValue([]);
    const { result } = renderHook(() => useHelpers());
    const helperMap = Object.fromEntries(result.current.map(entry => [entry.keyword, entry]));
    const options = { hash: { confirm: true } };

    render(helperMap.howler.componentCallback?.('hit-1', {}) as any);
    expect(screen.getByText('hit-1:normal')).toBeInTheDocument();

    render(helperMap.howler.componentCallback?.('', {}) as any);
    expect(screen.getByText('empty')).toBeInTheDocument();

    render(helperMap.render_json.componentCallback?.({ enabled: true }, {}) as any);
    expect(screen.getByText('{"enabled":true}')).toBeInTheDocument();

    render(helperMap.table.componentCallback?.(
      [
        { column: 'first_name', row: '1', value: 'Ada' },
        { column: 'last-name', row: '1', value: 'Lovelace' },
        { column: 'first_name', row: '2', value: 'Grace' }
      ],
      {}
    ) as any);
    expect(screen.getByText('First Name')).toBeInTheDocument();
    expect(screen.getByText('Last Name')).toBeInTheDocument();
    expect(screen.getByText('N/A')).toBeInTheDocument();

    render(helperMap.action.componentCallback?.('action-1', 'hit-9', options) as any);
    expect(screen.getByText('{"actionId":"action-1","hitId":"hit-9","rest":{"confirm":true}}')).toBeInTheDocument();
  });
});
