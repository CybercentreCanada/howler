/// <reference types="vitest" />
import { describe, expect, it } from 'vitest';
import { conf, language } from './markdownExtendedTokenProvider';

describe('markdownExtendedTokenProvider', () => {
  describe('conf', () => {
    it('exports a language configuration object', () => {
      expect(conf).toBeDefined();
      expect(typeof conf).toBe('object');
    });

    it('defines block comment markers', () => {
      expect(conf.comments?.blockComment).toEqual(['<!--', '-->']);
    });

    it('defines bracket pairs', () => {
      expect(Array.isArray(conf.brackets)).toBe(true);
      expect(conf.brackets.length).toBeGreaterThan(0);
    });

    it('defines auto-closing pairs', () => {
      expect(Array.isArray(conf.autoClosingPairs)).toBe(true);
    });

    it('defines folding markers', () => {
      expect(conf.folding?.markers?.start).toBeInstanceOf(RegExp);
      expect(conf.folding?.markers?.end).toBeInstanceOf(RegExp);
    });
  });

  describe('language', () => {
    it('exports a monarch language definition', () => {
      expect(language).toBeDefined();
      expect(typeof language).toBe('object');
    });

    it('has a root tokenizer state', () => {
      expect(language.tokenizer).toBeDefined();
      expect(Array.isArray(language.tokenizer.root)).toBe(true);
    });

    it('uses an empty string as the default token', () => {
      expect(language.defaultToken).toBe('');
    });

    it('includes Handlebars operators in the language definition', () => {
      const operators = (language as any).handlebars_operators as string[];
      expect(Array.isArray(operators)).toBe(true);
      expect(operators).toContain('#if');
      expect(operators).toContain('/if');
    });

    it('includes a handlebars tokenizer state', () => {
      expect(language.tokenizer).toHaveProperty('handlebars');
    });

    it('includes an html tokenizer state', () => {
      expect(language.tokenizer).toHaveProperty('html');
    });
  });
});
