import { useMonaco } from '@monaco-editor/react';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { FieldContext } from 'components/app/providers/FieldProvider';
import Fuse from 'fuse.js';
import type { languages } from 'monaco-editor';
import type { APILookups } from 'models/entities/generated/ApiType';
import { useContext, useEffect, useMemo } from 'react';
import { DEFAULT_QUERY } from 'utils/constants';

const isLookupKey = (key: string, lookups: APILookups): key is keyof APILookups => Object.hasOwn(lookups, key);

const useLuceneCompletionProvider = (): languages.CompletionItemProvider => {
  const { config } = useContext(ApiConfigContext);
  const monaco = useMonaco();
  const { hitFields, getHitFields } = useContext(FieldContext);

  useEffect(() => {
    void getHitFields();
  }, [getHitFields]);

  // Using fuse for fuzzy searching
  const fuse = useMemo(() => new Fuse(hitFields, { keys: ['key'], threshold: 0.4 }), [hitFields]);

  return {
    provideCompletionItems: async (model, position) => {
      if (!monaco) {
        return { suggestions: [] };
      }

      const line: string = model.getLineContent(position.lineNumber);

      const context = line.slice(0, position.column - 1);

      // Get what comes before, and the field we're intersted in autocompleting
      const before = context.replace(/^(.*?[^a-zA-Z._]?)[a-zA-Z._*]*$/, '$1');
      const portion = context.replace(/^.+?[^a-zA-Z._]([a-zA-Z._*]*)$/, '$1');

      // If the field is complete and we're autocompleting the value, we parse the field and see if it's an enum.
      // If it is, suggest the matching values
      if (before.trim().endsWith(':')) {
        const key = before.trim().replace(/^.*?[^a-zA-Z._]?([a-zA-Z._]+):$/, '$1');
        const lookupValues = isLookupKey(key, config.lookups) ? config.lookups[key] : undefined;

        if (Array.isArray(lookupValues)) {
          const _position = model.getWordUntilPosition(position);

          return {
            suggestions: lookupValues
              .filter((value): value is string => typeof value === 'string')
              .map(_value => ({
                label: _value,
                kind: monaco.languages.CompletionItemKind.Constant,
                insertText: _value,
                range: {
                  startLineNumber: position.lineNumber,
                  endLineNumber: position.lineNumber,
                  startColumn: _position.startColumn,
                  endColumn: _position.endColumn
                }
              }))
          };
        } else {
          const options = await api.search.facet.hit
            .post({ query: DEFAULT_QUERY, rows: 250, fields: [key] })
            .catch(() => null);

          const _position = model.getWordUntilPosition(position);

          return {
            suggestions: Object.keys(options?.[key] ?? {}).map(_value => ({
              label: _value,
              kind: monaco.languages.CompletionItemKind.Constant,
              insertText: `"${_value}"`,
              range: {
                startLineNumber: position.lineNumber,
                endLineNumber: position.lineNumber,
                startColumn: _position.startColumn,
                endColumn: _position.endColumn
              }
            }))
          };
        }
      }

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
          suggestions: fuzzyMatches.flatMap(({ item }) => {
            if (!item.key) {
              return [];
            }

            return [
              {
                label: item.key,
                detail: item.type,
                documentation: item.description,
                kind: monaco.languages.CompletionItemKind.Property,
                insertText: item.key + ':',
                range
              }
            ];
          })
        };
      } else {
        return {
          suggestions: hitFields.flatMap(_field => {
            if (!_field.key) {
              return [];
            }

            return [
              {
                label: _field.key,
                detail: _field.type,
                documentation: _field.description,
                kind: monaco.languages.CompletionItemKind.Property,
                insertText: _field.key + ':',
                range
              }
            ];
          })
        };
      }
    }
  };
};

export default useLuceneCompletionProvider;
