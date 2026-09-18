/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockFacetPost = vi.hoisted(() => vi.fn());

let mockMonaco: any = null;
let fieldContextValue: any = { hitFields: [], getHitFields: vi.fn() };
let apiConfigContextValue: any = { config: { lookups: {} } };
let recordSearchContextValue: any = { fzfSearch: false, queryHistory: {}, setFzfSearch: vi.fn() };
const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));

vi.mock('@monaco-editor/react', () => ({
  useMonaco: () => mockMonaco
}));

vi.mock('api', () => ({
  default: {
    search: {
      facet: {
        hit: {
          post: mockFacetPost
        }
      }
    }
  }
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: {}
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: unknown, selector: (ctx: any) => any) => selector(recordSearchContextValue)
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) {
        return apiConfigContextValue;
      }
      if (context === fieldContextToken) {
        return fieldContextValue;
      }
      return actual.useContext(context);
    }
  };
});

vi.mock('utils/utils', () => ({
  twitterShort: (value: string) => `short:${value}`
}));

import useEQLCompletionProvider from './eqlCompletionProvider';
import useHistoryCompletionProvider from './historyCompletionProvider';
import useLuceneCompletionProvider from './luceneCompletionProvider';
import useYamlCompletionProvider from './yamlCompletionProvider';

describe('advanced completion providers', () => {
  it('suggests lucene fields, lookup values, and facet values', async () => {
    const getHitFields = vi.fn();
    fieldContextValue = {
      hitFields: [
        { key: 'event.category', type: 'keyword', description: 'Event category' },
        { key: 'source.ip', type: 'ip', description: 'IP address' }
      ],
      getHitFields
    };
    apiConfigContextValue = { config: { lookups: { 'event.category': ['network', 'file', 7] } } };
    mockMonaco = { languages: { CompletionItemKind: { Constant: 'constant', Property: 'property', Reference: 'ref' } } };
    mockFacetPost.mockResolvedValue({ 'source.ip': { '1.1.1.1': 2, '8.8.8.8': 1 } });

    const { result } = renderHook(() => useLuceneCompletionProvider());
    const baseModel = {
      getLineContent: () => 'event.ca',
      getWordUntilPosition: () => ({ startColumn: 1, endColumn: 9 })
    };

    const fieldSuggestions = await result.current.provideCompletionItems(baseModel as any, { lineNumber: 1, column: 9 } as any);
    expect(getHitFields).toHaveBeenCalled();
    expect(fieldSuggestions.suggestions[0]).toMatchObject({
      label: 'event.category',
      insertText: 'event.category:',
      kind: 'property'
    });

    const lookupModel = {
      getLineContent: () => 'event.category: n',
      getWordUntilPosition: () => ({ startColumn: 17, endColumn: 18 })
    };
    const lookupSuggestions = await result.current.provideCompletionItems(lookupModel as any, { lineNumber: 1, column: 18 } as any);
    expect(lookupSuggestions.suggestions).toEqual(
      expect.arrayContaining([expect.objectContaining({ label: 'network', insertText: 'network', kind: 'constant' })])
    );

    apiConfigContextValue = { config: { lookups: {} } };
    const { result: facetResult } = renderHook(() => useLuceneCompletionProvider());
    const facetModel = {
      getLineContent: () => 'source.ip: 1',
      getWordUntilPosition: () => ({ startColumn: 12, endColumn: 13 })
    };
    const facetSuggestions = await facetResult.current.provideCompletionItems(facetModel as any, { lineNumber: 1, column: 12 } as any);
    expect(mockFacetPost).toHaveBeenCalled();
    expect(facetSuggestions.suggestions[0]).toMatchObject({ label: '1.1.1.1', insertText: '"1.1.1.1"' });
  });

  it('returns no lucene suggestions until monaco is available', async () => {
    mockMonaco = null;
    fieldContextValue = { hitFields: [], getHitFields: vi.fn() };
    apiConfigContextValue = { config: { lookups: {} } };

    const { result } = renderHook(() => useLuceneCompletionProvider());
    await expect(
      result.current.provideCompletionItems({ getLineContent: () => '', getWordUntilPosition: () => ({ startColumn: 1, endColumn: 1 }) } as any, {
        lineNumber: 1,
        column: 1
      } as any)
    ).resolves.toEqual({ suggestions: [] });
  });

  it('suggests yaml fields, eql event categories, and query history', async () => {
    mockMonaco = { languages: { CompletionItemKind: { Constant: 'constant', Property: 'property', Reference: 'ref' } } };
    fieldContextValue = {
      hitFields: [
        { key: 'event.category', type: 'keyword', description: 'Event category' },
        { key: 'host.name', type: 'keyword', description: 'Host name' }
      ]
    };
    recordSearchContextValue = {
      fzfSearch: true,
      queryHistory: {
        'event.category:network': '2026-09-18',
        'host.name:server-1': '2026-09-17'
      }
    };

    const yaml = renderHook(() => useYamlCompletionProvider());
    expect(
      yaml.result.current.provideCompletionItems(
        { getLineContent: () => 'event.cat', getWordUntilPosition: () => ({ startColumn: 1, endColumn: 9 }) } as any,
        { lineNumber: 1, column: 9 } as any
      ).suggestions[0]
    ).toMatchObject({ label: 'event.category', insertText: 'event.category' });

    const eql = renderHook(() => useEQLCompletionProvider());
    expect(
      eql.result.current.provideCompletionItems(
        { getLineContent: () => '[', getWordUntilPosition: () => ({ startColumn: 1, endColumn: 1 }) } as any,
        { lineNumber: 1, column: 2 } as any
      ).suggestions
    ).toEqual(expect.arrayContaining([expect.objectContaining({ label: 'network' }), expect.objectContaining({ label: 'any' })]));

    const history = renderHook(() => useHistoryCompletionProvider());
    const historySuggestions = await history.result.current.provideCompletionItems(
      {
        getLineContent: () => 'event',
        getWordAtPosition: () => ({ word: 'event' })
      } as any,
      { lineNumber: 1, column: 6 } as any
    );
    expect(historySuggestions.suggestions[0]).toMatchObject({
      label: 'event.category:network',
      kind: 'ref',
      detail: 'short:2026-09-18'
    });
  });
});
