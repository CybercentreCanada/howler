import { useMonaco } from '@monaco-editor/react';
import { FieldContext } from 'components/app/providers/FieldProvider';
import Fuse from 'fuse.js';
import type { languages } from 'monaco-editor';
import { useContext, useMemo } from 'react';

const useYamlCompletionProvider = (): languages.CompletionItemProvider => {
  const monaco = useMonaco();
  const { hitFields } = useContext(FieldContext);

  const fuse = useMemo(() => new Fuse(hitFields, { keys: ['key'], threshold: 0.4 }), [hitFields]);

  return {
    provideCompletionItems: (model, position) => {
      const line: string = model.getLineContent(position.lineNumber);

      const context = line.slice(0, position.column - 1);

      const before = context.replace(/^(.*?[^a-zA-Z._]?)[a-zA-Z._]+$/, '$1');
      const portion = context.replace(/^.+?[^a-zA-Z._]([a-zA-Z._]+)$/, '$1');

      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: before.length + 1,
        endColumn: before.length + portion.length
      };

      // If we have something to search with, use it, otherwise just suggest everything
      if (portion) {
        const fuzzyMatches = fuse.search(portion);
        return {
          suggestions: fuzzyMatches.map(({ item }) => ({
            label: item.key,
            detail: item.type,
            documentation: item.description,
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: item.key,
            range
          }))
        };
      } else {
        return {
          suggestions: hitFields.map(_field => ({
            label: _field.key,
            detail: _field.type,
            documentation: _field.description,
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: _field.key,
            range
          }))
        };
      }
    }
  };
};

export default useYamlCompletionProvider;
