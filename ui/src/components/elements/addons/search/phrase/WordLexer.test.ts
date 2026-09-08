/// <reference types="vitest" />
// @ts-nocheck
import { describe, expect, it } from 'vitest';
import WordLexer from './word/WordLexer';

describe('WordLexer', () => {
  const lexer = new WordLexer();

  describe('parse', () => {
    it('parses a single word', () => {
      const result = lexer.parse('hello');
      expect(result.tokens).toHaveLength(2); // word + eop
      expect(result.tokens[0].type).toBe('word');
      expect(result.tokens[0].value).toBe('hello');
    });

    it('parses two words separated by a space', () => {
      const result = lexer.parse('hello world');
      const nonEop = result.tokens.filter(t => t.type !== 'eop');
      expect(nonEop.some(t => t.type === 'word' && t.value === 'hello')).toBe(true);
      expect(nonEop.some(t => t.type === 'word' && t.value === 'world')).toBe(true);
    });

    it('always ends with an eop token', () => {
      const result = lexer.parse('foo bar');
      const last = result.tokens[result.tokens.length - 1];
      expect(last.type).toBe('eop');
      expect(last.value).toBe('');
    });

    it('returns an eop-only token list for empty input', () => {
      const result = lexer.parse('');
      expect(result.tokens).toHaveLength(1);
      expect(result.tokens[0].type).toBe('eop');
    });

    it('sets cursor correctly', () => {
      const result = lexer.parse('hello', 3);
      expect(result.cursor).toBe(3);
    });

    it('sets current token for cursor in the middle of a word', () => {
      const result = lexer.parse('hello', 3);
      expect(result.current?.type).toBe('word');
    });

    it('provides suggest token for current cursor position', () => {
      const result = lexer.parse('hello world', 7);
      expect(result.suggest).toBeDefined();
      expect(result.suggest.token).toBeDefined();
    });

    it('sets startIndex/endIndex correctly on word tokens', () => {
      const result = lexer.parse('hi');
      const wordToken = result.tokens.find(t => t.type === 'word');
      expect(wordToken.startIndex).toBe(0);
      expect(wordToken.endIndex).toBe(1);
    });

    it('whitespace tokens have correct type', () => {
      const result = lexer.parse('a b');
      const wsToken = result.tokens.find(t => t.type === 'whitespace');
      expect(wsToken).toBeDefined();
    });
  });
});
