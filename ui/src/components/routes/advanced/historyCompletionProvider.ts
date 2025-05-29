import { useMonaco } from '@monaco-editor/react';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import Fuse from 'fuse.js';
import type { languages } from 'monaco-editor';
import { useMemo } from 'react';
import { useContextSelector } from 'use-context-selector';
import { twitterShort } from 'utils/utils';

const useHistoryCompletionProvider = (): languages.CompletionItemProvider => {
  const monaco = useMonaco();
  const fzfSearch = useContextSelector(HitSearchContext, ctx => ctx?.fzfSearch);
  const queryHistory = useContextSelector(HitSearchContext, ctx => ctx?.queryHistory ?? {});

  // Using fuse for fuzzy searching
  const fuse = useMemo(() => new Fuse(Object.keys(queryHistory), { keys: ['key'], threshold: 0.4 }), [queryHistory]);

  return {
    provideCompletionItems: async (model, position) => {
      if (!fzfSearch) {
        return { suggestions: [] };
      }

      const line: string = model.getLineContent(position.lineNumber);

      const context = line.slice(0, position.column - 1);

      // Get what comes before, and the field we're intersted in autocompleting
      const before = context.replace(/^(.*?[^a-zA-Z._]?)[a-zA-Z._*]*$/, '$1');
      const portion = context.replace(/^.+?[^a-zA-Z._]([a-zA-Z._*]*)$/, '$1');

      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: before.length + 1,
        endColumn: before.length + portion.length
      };

      const currentWord = model.getWordAtPosition(position);
      const query = currentWord ? currentWord.word : '';

      const fuzzyResults = fuse.search(query);

      // Map the fuzzy search results to Monaco completion items
      const suggestions = fuzzyResults.map(result => {
        return {
          label: result.item, // The query string from previous searches
          kind: monaco.languages.CompletionItemKind.Reference, // Simple reference type
          insertText: result.item, // Insert the plain text as it is
          detail: twitterShort(queryHistory[result.item]), // Optional additional detail
          range
        };
      });

      return {
        suggestions
      };
    }
  };
};

export default useHistoryCompletionProvider;
