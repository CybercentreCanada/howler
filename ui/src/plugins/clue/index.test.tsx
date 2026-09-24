import { describe, expect, it } from 'vitest';
import CluePlugin from './index';

describe('Clue plugin', () => {
  it('keeps its provider component identity stable', () => {
    const plugin = new CluePlugin();

    expect(plugin.provider()).toBe(plugin.provider());
  });
});
