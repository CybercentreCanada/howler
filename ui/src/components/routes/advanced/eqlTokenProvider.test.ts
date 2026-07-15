/// <reference types="vitest" />
import { describe, expect, it } from 'vitest';
import TOKEN_PROVIDER from './eqlTokenProvider';

describe('EQL token provider', () => {
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

  it('uses "invalid" as the defaultToken', () => {
    expect(TOKEN_PROVIDER.defaultToken).toBe('invalid');
  });

  it('defines the expected EQL keywords', () => {
    const kws = TOKEN_PROVIDER.keywords as string[];
    expect(kws).toContain('where');
    expect(kws).toContain('not');
    expect(kws).toContain('in');
    expect(kws).toContain('head');
    expect(kws).toContain('tail');
  });

  it('defines boolean operators', () => {
    const booleans = TOKEN_PROVIDER.booleans as string[];
    expect(booleans).toContain('and');
    expect(booleans).toContain('or');
  });

  it('has includeLF set to true', () => {
    expect(TOKEN_PROVIDER.includeLF).toBe(true);
  });
});
