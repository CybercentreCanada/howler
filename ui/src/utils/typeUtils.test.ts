/// <reference types="vitest" />
import { describe, expect, it } from 'vitest';
import { isCase, isEvent, isHit } from './typeUtils';

describe('typeUtils', () => {
  it('identifies hits by __index', () => {
    expect(isHit({ __index: 'hit' } as any)).toBe(true);
    expect(isHit({ __index: 'event' } as any)).toBe(false);
  });

  it('identifies cases by __index', () => {
    expect(isCase({ __index: 'case' } as any)).toBe(true);
    expect(isCase({ __index: 'hit' } as any)).toBe(false);
  });

  it('identifies events by __index', () => {
    expect(isEvent({ __index: 'event' } as any)).toBe(true);
    expect(isEvent({ __index: 'case' } as any)).toBe(false);
  });

  it('returns false for nullish values and objects without an index', () => {
    expect(isHit(null as any)).toBe(false);
    expect(isCase(undefined as any)).toBe(false);
    expect(isEvent({} as any)).toBe(false);
  });
});
