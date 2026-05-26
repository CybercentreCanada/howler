/// <reference types="vitest" />
import { describe, expect, it } from 'vitest';
import {
  maxLenStr,
  nameToInitials,
  safeFieldValue,
  safeFieldValueURI,
  safeStringPropertyCompare,
  sanitizeLuceneQuery,
  sanitizeMultilineLucene,
  validateRegex
} from './stringUtils';

describe('nameToInitials', () => {
  it('returns initials from a standard first-last name', () => {
    expect(nameToInitials('John Doe')).toEqual(['J', 'D']);
  });

  it('returns a single initial when there is only one word', () => {
    expect(nameToInitials('John')).toEqual(['J']);
  });

  it('uses only the first two words even when there are more', () => {
    expect(nameToInitials('John Middle Doe')).toEqual(['J', 'M']);
  });

  it('reverses order when the name is in "last, first" comma format', () => {
    // "Smith, John" → parts = ["Smith,", "John"] → reversed → ["John", "Smith,"] → initials ["J", "S"]
    expect(nameToInitials('Smith, John')).toEqual(['J', 'S']);
  });

  it('returns uppercase initials regardless of input case', () => {
    expect(nameToInitials('alice bob')).toEqual(['A', 'B']);
  });
});

describe('maxLenStr', () => {
  it('returns the string unchanged when shorter than the limit', () => {
    expect(maxLenStr('hello', 10)).toBe('hello');
  });

  it('returns the string unchanged when length equals the limit', () => {
    expect(maxLenStr('hello', 5)).toBe('hello');
  });

  it('truncates and appends "..." when string exceeds the limit', () => {
    expect(maxLenStr('hello world', 8)).toBe('hello...');
  });

  it('handles an empty string', () => {
    expect(maxLenStr('', 5)).toBe('');
  });

  it('truncation accounts for the three-character ellipsis', () => {
    // len=6 → keeps first 3 chars then "..."
    expect(maxLenStr('abcdefgh', 6)).toBe('abc...');
  });
});

describe('safeFieldValue', () => {
  it('wraps a plain string in double quotes', () => {
    expect(safeFieldValue('test')).toBe('"test"');
  });

  it('escapes backslashes', () => {
    expect(safeFieldValue('back\\slash')).toBe('"back\\\\slash"');
  });

  it('escapes embedded double quotes', () => {
    expect(safeFieldValue('say "hello"')).toBe('"say \\"hello\\""');
  });

  it('converts a number to a quoted string', () => {
    expect(safeFieldValue(42)).toBe('"42"');
  });

  it('converts a boolean to a quoted string', () => {
    expect(safeFieldValue(true)).toBe('"true"');
  });

  it('escapes backslash before escaping quotes (order matters)', () => {
    expect(safeFieldValue('\\"')).toBe('"\\\\\\"\"');
  });
});

describe('safeFieldValueURI', () => {
  it('URI-encodes the safe field value of a plain string', () => {
    expect(safeFieldValueURI('hello')).toBe(encodeURIComponent('"hello"'));
  });

  it('URI-encodes special characters', () => {
    expect(safeFieldValueURI('hello world')).toBe(encodeURIComponent('"hello world"'));
  });

  it('handles strings that already contain lucene special chars', () => {
    const input = 'field:value';
    expect(safeFieldValueURI(input)).toBe(encodeURIComponent(safeFieldValue(input)));
  });
});

describe('sanitizeLuceneQuery', () => {
  it('escapes colons', () => {
    expect(sanitizeLuceneQuery('field:value')).toBe('field\\:value');
  });

  it('escapes forward slashes', () => {
    expect(sanitizeLuceneQuery('path/to')).toBe('path\\/to');
  });

  it('escapes opening parenthesis', () => {
    expect(sanitizeLuceneQuery('(term)')).toBe('\\(term\\)');
  });

  it('escapes square brackets', () => {
    expect(sanitizeLuceneQuery('[a TO b]')).toBe('\\[a TO b\\]');
  });

  it('escapes curly braces', () => {
    expect(sanitizeLuceneQuery('{a TO b}')).toBe('\\{a TO b\\}');
  });

  it('escapes carets', () => {
    expect(sanitizeLuceneQuery('term^2')).toBe('term\\^2');
  });

  it('escapes double-ampersand (&&)', () => {
    expect(sanitizeLuceneQuery('a && b')).toBe('a \\&& b');
  });

  it('escapes double-pipe (||)', () => {
    expect(sanitizeLuceneQuery('a || b')).toBe('a \\|| b');
  });

  it('leaves a plain alphanumeric string unchanged', () => {
    expect(sanitizeLuceneQuery('plainterm')).toBe('plainterm');
  });
});

describe('safeStringPropertyCompare', () => {
  const compare = safeStringPropertyCompare('name');

  it('returns a negative number when a sorts before b', () => {
    expect(compare({ name: 'Alice' }, { name: 'Bob' })).toBeLessThan(0);
  });

  it('returns a positive number when a sorts after b', () => {
    expect(compare({ name: 'Bob' }, { name: 'Alice' })).toBeGreaterThan(0);
  });

  it('returns 0 for equal strings', () => {
    expect(compare({ name: 'Alice' }, { name: 'Alice' })).toBe(0);
  });

  it('returns 1 when only a has the property', () => {
    expect(compare({ name: 'Alice' }, {})).toBe(1);
  });

  it('returns 0 when only b has the property', () => {
    expect(compare({}, { name: 'Bob' })).toBe(0);
  });

  it('returns 0 when neither object has the property', () => {
    expect(compare({}, {})).toBe(0);
  });

  it('supports nested property paths', () => {
    const nestedCompare = safeStringPropertyCompare('user.name');
    expect(nestedCompare({ user: { name: 'Alice' } }, { user: { name: 'Bob' } })).toBeLessThan(0);
  });
});

describe('sanitizeMultilineLucene', () => {
  it('removes a trailing inline comment', () => {
    expect(sanitizeMultilineLucene('query # comment')).toBe('query ');
  });

  it('removes a full-line comment', () => {
    expect(sanitizeMultilineLucene('# full line\nquery')).toBe('\nquery');
  });

  it('collapses two or more consecutive newlines into one', () => {
    expect(sanitizeMultilineLucene('a\n\n\nb')).toBe('a\nb');
  });

  it('collapses exactly two consecutive newlines', () => {
    expect(sanitizeMultilineLucene('a\n\nb')).toBe('a\nb');
  });

  it('leaves a clean single-line query unchanged', () => {
    expect(sanitizeMultilineLucene('howler.status:open')).toBe('howler.status:open');
  });
});

describe('validateRegex', () => {
  it('returns true for a valid regex pattern', () => {
    expect(validateRegex('[a-z]+')).toBe(true);
  });

  it('returns true for an empty string (valid zero-length pattern)', () => {
    expect(validateRegex('')).toBe(true);
  });

  it('returns false for an invalid regex pattern', () => {
    expect(validateRegex('[unclosed')).toBe(false);
  });

  it('returns true for a complex but valid regex', () => {
    expect(validateRegex('^(\\d{4})-(\\d{2})-(\\d{2})$')).toBe(true);
  });

  it('returns true for a pattern with quantifiers', () => {
    expect(validateRegex('a{2,5}')).toBe(true);
  });
});
