/// <reference types="vitest" />
import { describe, expect, it } from 'vitest';
import type { PhraseToken } from '.';
import PhraseConsumer from './PhraseConsumer';
import PhraseLexer from './PhraseLexer';

class WordConsumer extends PhraseConsumer<TestLexer> {
  lock(lexer: TestLexer) {
    return /^[A-Za-z[]/.test(lexer.bufferValue());
  }

  consume(lexer: TestLexer): PhraseToken | null {
    const value = this.bufferValue();

    if (value.startsWith('[') && value.endsWith(']')) {
      return {
        type: 'group',
        value,
        startIndex: lexer.start(),
        endIndex: lexer.end(),
        children: [
          {
            type: 'open',
            value: '[',
            startIndex: lexer.start(),
            endIndex: lexer.start()
          },
          {
            type: 'value',
            value: value.slice(1, -1),
            startIndex: lexer.start() + 1,
            endIndex: lexer.end() - 1
          },
          {
            type: 'close',
            value: ']',
            startIndex: lexer.end(),
            endIndex: lexer.end()
          }
        ]
      };
    }

    if (lexer.aheadStartsWithAny(false, ' ') || lexer.aheadIsEmpty()) {
      return { type: 'word', value, startIndex: lexer.start(), endIndex: lexer.end() };
    }

    return null;
  }
}

class SpaceConsumer extends PhraseConsumer<TestLexer> {
  lock(lexer: TestLexer) {
    return lexer.bufferValue() === ' ';
  }

  consume(lexer: TestLexer): PhraseToken | null {
    return { type: 'space', value: ' ', startIndex: lexer.start(), endIndex: lexer.end() };
  }
}

class TestLexer extends PhraseLexer {
  consumers() {
    return [new SpaceConsumer(), new WordConsumer()];
  }
}

describe('PhraseLexer', () => {
  it('parses tokens and suggestion context from the cursor', () => {
    const lexer = new TestLexer();
    const analysis = lexer.parse('alpha beta', 7);

    expect(analysis.tokens).toEqual([
      { type: 'word', value: 'alpha', startIndex: 0, endIndex: 4 },
      { type: 'space', value: ' ', startIndex: 5, endIndex: 5 },
      { type: 'word', value: 'beta', startIndex: 6, endIndex: 9 },
      { type: 'eop', startIndex: 10, endIndex: 10, value: '' }
    ]);
    expect(analysis.parent.value).toBe('beta');
    expect(analysis.current.value).toBe('beta');
    expect(analysis.suggest.value).toBe('b');
  });

  it('flattens child tokens when selecting the current token', () => {
    const lexer = new TestLexer();
    const analysis = lexer.parse('[xy]', 1);

    expect(analysis.parent.type).toBe('group');
    expect(analysis.current).toMatchObject({ type: 'value', value: 'xy' });
    expect(analysis.suggest.parent).toMatchObject({ type: 'group', value: '[xy]' });
  });

  it('exposes buffer navigation helpers while parsing', () => {
    const lexer = new TestLexer();
    lexer.parse('one two');

    expect(lexer.start()).toBe(7);
    expect(lexer.end()).toBe(6);
    expect(lexer.buffer()).toEqual([]);
    expect(lexer.ahead()).toBe('');
    expect(lexer.aheadIsEmpty()).toBe(true);
    expect(lexer.behind()).toBe('');
    expect(lexer.behindEndsWithAny(false, '')).toBe(true);
    expect(lexer.testAhead(/^$/)).toBe(true);
    expect(lexer.testBehind(/^$/)).toBe(true);
  });
});
