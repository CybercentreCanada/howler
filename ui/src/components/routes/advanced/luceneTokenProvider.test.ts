import { describe, expect, it } from 'vitest';
import TOKEN_PROVIDER from './luceneTokenProvider';

describe('Lucene token provider', () => {
  it('exports a non-null object', () => {
    expect(TOKEN_PROVIDER).toBeDefined();
    expect(TOKEN_PROVIDER).not.toBeNull();
    expect(typeof TOKEN_PROVIDER).toBe('object');
  });

  it('has a "root" tokenizer entry', () => {
    expect(TOKEN_PROVIDER.tokenizer).toBeDefined();
    expect(TOKEN_PROVIDER.tokenizer.root).toBeDefined();
    expect(Array.isArray(TOKEN_PROVIDER.tokenizer.root)).toBe(true);
  });

  it('defines the expected operators', () => {
    const ops = TOKEN_PROVIDER.operators as string[];
    expect(ops).toContain('-');
    expect(ops).toContain('&&');
    expect(ops).toContain('||');
    expect(ops).toContain(':');
  });

  it('defines the expected keywords (AND, OR, NOT)', () => {
    const kws = TOKEN_PROVIDER.keywords as string[];
    expect(kws).toContain('AND');
    expect(kws).toContain('OR');
    expect(kws).toContain('NOT');
  });

  it('uses "default" as the defaultToken', () => {
    expect(TOKEN_PROVIDER.defaultToken).toBe('default');
  });

  it('includes a string tokenizer state for quoted values', () => {
    expect(TOKEN_PROVIDER.tokenizer).toHaveProperty('string');
  });
});
