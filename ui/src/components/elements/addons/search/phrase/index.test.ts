/// <reference types="vitest" />
import { describe, expect, it } from 'vitest';
import { PhraseBuffer } from '.';

describe('PhraseBuffer', () => {
  it('builds tokens from appended content', () => {
    const buffer = new PhraseBuffer('word').init(3, ['a']).append('b').append('c');
    expect(buffer.value()).toBe('abc');
    expect(buffer.start()).toBe(3);
    expect(buffer.end()).toBe(6);
    expect(buffer.token()).toEqual({ type: 'word', value: 'abc', startIndex: 3, endIndex: 5 });
  });

  it('allows explicit start and end overrides and returns null for empty buffers', () => {
    const buffer = new PhraseBuffer().init(0);
    expect(buffer.token()).toBeNull();
    buffer.start(5);
    buffer.end(9);
    expect(buffer.start()).toBe(5);
    expect(buffer.end()).toBe(9);
  });
});
