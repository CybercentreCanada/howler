/// <reference types="vitest" />
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  bytesToSize,
  compareTimestamp,
  convertCustomDateRangeToLucene,
  convertDateToLucene,
  convertLuceneToDate,
  delay,
  flattenDeep,
  formatDate,
  getProvider,
  getTimeRange,
  hashCode,
  humanReadableNumber,
  removeEmpty,
  searchObject,
  searchResultsDisplay,
  sortByTimestamp,
  stringToColor,
  tryParse,
  twitterShort
} from './utils';

describe('bytesToSize', () => {
  it('returns "0 B" for 0', () => {
    expect(bytesToSize(0)).toBe('0 B');
  });

  it('returns "0 B" for null', () => {
    expect(bytesToSize(null)).toBe('0 B');
  });

  it('formats bytes', () => {
    expect(bytesToSize(512)).toBe('512 B');
  });

  it('formats kilobytes', () => {
    expect(bytesToSize(1024)).toBe('1 KB');
  });

  it('formats megabytes', () => {
    expect(bytesToSize(1024 * 1024)).toBe('1 MB');
  });

  it('formats gigabytes', () => {
    expect(bytesToSize(1024 * 1024 * 1024)).toBe('1 GB');
  });
});

describe('humanReadableNumber', () => {
  it('returns "0 " for 0', () => {
    expect(humanReadableNumber(0)).toBe('0 ');
  });

  it('returns "0 " for null', () => {
    expect(humanReadableNumber(null)).toBe('0 ');
  });

  it('returns the number with a trailing space for values below 1000', () => {
    expect(humanReadableNumber(500)).toBe('500 ');
  });

  it('formats thousands with "k"', () => {
    expect(humanReadableNumber(1000)).toBe('1k ');
  });

  it('formats millions with "m"', () => {
    expect(humanReadableNumber(1_000_000)).toBe('1m ');
  });
});

describe('compareTimestamp', () => {
  it('returns a negative number when a is earlier than b', () => {
    expect(compareTimestamp('2021-01-01T00:00:00Z', '2021-01-02T00:00:00Z')).toBeLessThan(0);
  });

  it('returns a positive number when a is later than b', () => {
    expect(compareTimestamp('2021-01-02T00:00:00Z', '2021-01-01T00:00:00Z')).toBeGreaterThan(0);
  });

  it('returns 0 for identical timestamps', () => {
    expect(compareTimestamp('2021-01-01T00:00:00Z', '2021-01-01T00:00:00Z')).toBe(0);
  });

  it('returns a difference in seconds', () => {
    // 86400 seconds = 1 day
    expect(compareTimestamp('2021-01-02T00:00:00Z', '2021-01-01T00:00:00Z')).toBe(86400);
  });
});

describe('hashCode', () => {
  it('returns a number', () => {
    expect(typeof hashCode('hello')).toBe('number');
  });

  it('returns the same value for the same input', () => {
    expect(hashCode('hello')).toBe(hashCode('hello'));
  });

  it('returns different values for different inputs', () => {
    expect(hashCode('hello')).not.toBe(hashCode('world'));
  });

  it('returns 0 for an empty string', () => {
    expect(hashCode('')).toBe(0);
  });
});

describe('sortByTimestamp', () => {
  it('returns an empty array for an empty input', () => {
    expect(sortByTimestamp([])).toEqual([]);
  });

  it('sorts items in descending timestamp order (most recent first)', () => {
    const items = [
      { timestamp: '2021-01-01T00:00:00Z' },
      { timestamp: '2021-03-01T00:00:00Z' },
      { timestamp: '2021-02-01T00:00:00Z' }
    ];
    const sorted = sortByTimestamp(items);
    expect(sorted[0].timestamp).toBe('2021-03-01T00:00:00Z');
    expect(sorted[2].timestamp).toBe('2021-01-01T00:00:00Z');
  });

  it('does not mutate the original array', () => {
    const original = [{ timestamp: '2021-01-01T00:00:00Z' }, { timestamp: '2021-03-01T00:00:00Z' }];
    const copy = [...original];
    sortByTimestamp(original);
    expect(original).toEqual(copy);
  });

  it('handles items with missing timestamps', () => {
    const items = [{ timestamp: '2021-01-01T00:00:00Z' }, {}];
    expect(() => sortByTimestamp(items)).not.toThrow();
  });
});

describe('getTimeRange', () => {
  it('returns [earliest, latest] from an array of timestamps', () => {
    const timestamps = ['2021-03-01T00:00:00Z', '2021-01-01T00:00:00Z', '2021-02-01T00:00:00Z'];
    const [start, end] = getTimeRange(timestamps);
    expect(start).toBe('2021-01-01T00:00:00Z');
    expect(end).toBe('2021-03-01T00:00:00Z');
  });

  it('returns the same value for both when given a single timestamp', () => {
    const [start, end] = getTimeRange(['2021-01-01T00:00:00Z']);
    expect(start).toBe(end);
  });
});

describe('removeEmpty', () => {
  it('removes null values from a flat object', () => {
    expect(removeEmpty({ a: null, b: 'val' })).toEqual({ b: 'val' });
  });

  it('removes undefined values from a flat object', () => {
    expect(removeEmpty({ a: undefined, b: 'val' })).toEqual({ b: 'val' });
  });

  it('recursively removes null values from nested objects', () => {
    expect(removeEmpty({ nested: { a: null, b: 'val' } })).toEqual({ nested: { b: 'val' } });
  });

  it('handles an empty object', () => {
    expect(removeEmpty({})).toEqual({});
  });

  it('handles null input gracefully', () => {
    expect(removeEmpty(null)).toEqual({});
  });

  it('keeps arrays as-is', () => {
    const result = removeEmpty({ arr: [1, 2, 3] });
    expect(result.arr).toEqual([1, 2, 3]);
  });
});

describe('searchObject', () => {
  const obj = { name: 'Alice', role: 'admin', nested: { city: 'Ottawa' } };

  it('returns the full object when query is empty', () => {
    const result = searchObject(obj, '');
    expect(result).toMatchObject(obj);
  });

  it('returns matching entries for a key match', () => {
    const result = searchObject(obj, 'name') as any;
    expect(result.name).toBe('Alice');
  });

  it('returns matching entries for a value match', () => {
    const result = searchObject(obj, 'Alice') as any;
    expect(result.name).toBe('Alice');
  });

  it('returns an empty object when nothing matches', () => {
    const result = searchObject(obj, 'zzznomatch');
    expect(result).toEqual({});
  });

  it('returns flat result when returnFlat=true', () => {
    const result = searchObject(obj, 'city', true) as any;
    expect(result['nested.city']).toBe('Ottawa');
  });

  it('returns full flat object when query is empty and returnFlat=true', () => {
    const result = searchObject({ a: 1 }, '', true) as any;
    expect(result.a).toBe(1);
  });

  it('handles an invalid regex gracefully by returning the full object', () => {
    const result = searchObject(obj, '[invalid');
    expect(result).toMatchObject(obj);
  });
});

describe('convertDateToLucene', () => {
  it('returns "[now-1d TO now]" for a 1-day range', () => {
    expect(convertDateToLucene('date.range.1.day')).toBe('[now-1d TO now]');
  });

  it('returns "[now-1w TO now]" for a 1-week range', () => {
    expect(convertDateToLucene('date.range.1.week')).toBe('[now-1w TO now]');
  });

  it('returns "[now-1M TO now]" for a 1-month range', () => {
    expect(convertDateToLucene('date.range.1.month')).toBe('[now-1M TO now]');
  });

  it('returns "[now-1y TO now]" for a 1-year range', () => {
    expect(convertDateToLucene('date.range.1.year')).toBe('[now-1y TO now]');
  });

  it('returns "*" for the "all" range', () => {
    expect(convertDateToLucene('date.range.all')).toBe('*');
  });

  it('returns the default 1-day range when input does not start with "date.range."', () => {
    expect(convertDateToLucene('something.else')).toBe('[now-1d TO now]');
  });

  it('uses the day unit as fallback for an unknown period type', () => {
    expect(convertDateToLucene('date.range.3.unknown')).toBe('[now-3d TO now]');
  });

  it('handles multi-unit amounts', () => {
    expect(convertDateToLucene('date.range.3.day')).toBe('[now-3d TO now]');
  });
});

describe('convertCustomDateRangeToLucene', () => {
  it('formats a custom date range', () => {
    expect(convertCustomDateRangeToLucene('2021-01-01', '2021-12-31')).toBe('[2021-01-01 TO 2021-12-31]');
  });

  it('works with ISO datetime strings', () => {
    expect(convertCustomDateRangeToLucene('2021-01-01T00:00:00Z', '2021-12-31T23:59:59Z')).toBe(
      '[2021-01-01T00:00:00Z TO 2021-12-31T23:59:59Z]'
    );
  });
});

describe('convertLuceneToDate', () => {
  it('converts a 1-day lucene range back to "date.range.1.day"', () => {
    expect(convertLuceneToDate('event.created:[now-1d TO now]')).toBe('date.range.1.day');
  });

  it('converts a 1-week lucene range back to "date.range.1.week"', () => {
    expect(convertLuceneToDate('event.created:[now-1w TO now]')).toBe('date.range.1.week');
  });

  it('converts a 1-month lucene range back to "date.range.1.month"', () => {
    expect(convertLuceneToDate('event.created:[now-1M TO now]')).toBe('date.range.1.month');
  });

  it('returns the input unchanged when there is no colon (not a field query)', () => {
    expect(convertLuceneToDate('*')).toBe('*');
  });

  it('falls back to "day" for an unrecognised unit suffix', () => {
    expect(convertLuceneToDate('event.created:[now-5z TO now]')).toBe('date.range.5.day');
  });
});

describe('tryParse', () => {
  it('parses valid JSON and returns the value', () => {
    expect(tryParse('{"a":1}')).toEqual({ a: 1 });
  });

  it('parses a JSON array', () => {
    expect(tryParse('[1,2,3]')).toEqual([1, 2, 3]);
  });

  it('returns the raw string when JSON is invalid', () => {
    expect(tryParse('not json')).toBe('not json');
  });

  it('parses a quoted JSON string', () => {
    expect(tryParse('"hello"')).toBe('hello');
  });

  it('returns the raw string for partially-valid JSON', () => {
    expect(tryParse('{invalid}')).toBe('{invalid}');
  });
});

describe('flattenDeep', () => {
  it('flattens a simple nested object', () => {
    const result = flattenDeep({ a: { b: 1 } });
    expect(result).toEqual({ 'a.b': 1 });
  });

  it('leaves a flat object unchanged', () => {
    const result = flattenDeep({ a: 1, b: 2 });
    expect(result).toEqual({ a: 1, b: 2 });
  });

  it('flattens arrays of objects by merging values under a common key', () => {
    const result = flattenDeep({ items: [{ id: 'x' }, { id: 'y' }] });
    expect(result['items.id']).toEqual(['x', 'y']);
  });

  it('keeps a primitive array as-is', () => {
    const result = flattenDeep({ tags: ['a', 'b', 'c'] });
    expect(result.tags).toEqual(['a', 'b', 'c']);
  });

  it('handles an empty object', () => {
    expect(flattenDeep({})).toEqual({});
  });
});

describe('formatDate', () => {
  it('returns "?" for a falsy value', () => {
    expect(formatDate(null as any)).toBe('?');
  });

  it('returns "?" for an empty string', () => {
    expect(formatDate('')).toBe('?');
  });

  it('formats an ISO string as UTC in YYYY/MM/DD HH:mm:ss format', () => {
    // 2021-06-15T12:30:45Z → UTC → "2021/06/15 12:30:45"
    expect(formatDate('2021-06-15T12:30:45Z')).toBe('2021/06/15 12:30:45');
  });

  it('formats a Date object correctly', () => {
    const date = new Date('2023-01-01T00:00:00Z');
    expect(formatDate(date)).toBe('2023/01/01 00:00:00');
  });

  it('formats a unix timestamp (ms) correctly', () => {
    // 1000ms = 1970-01-01T00:00:01Z
    expect(formatDate(1000)).toBe('1970/01/01 00:00:01');
  });

  it('returns "?" for a numeric 0 (treated as falsy by the guard)', () => {
    expect(formatDate(0 as any)).toBe('?');
  });
});

describe('twitterShort', () => {
  it('returns "?" for a falsy value', () => {
    expect(twitterShort(null as any)).toBe('?');
  });

  it('returns "?" for the literal string "?"', () => {
    expect(twitterShort('?' as any)).toBe('?');
  });

  it('returns a non-empty relative string for a recent date', () => {
    const result = twitterShort(new Date().toISOString());
    expect(result).toBeTruthy();
    expect(typeof result).toBe('string');
  });

  it('returns "a few seconds ago" for a date just in the past', () => {
    const recent = new Date(Date.now() - 2000).toISOString();
    expect(twitterShort(recent)).toBe('a few seconds ago');
  });

  it('returns a sensible relative string for a date one year in the past', () => {
    const oneYearAgo = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString();
    const result = twitterShort(oneYearAgo);
    expect(result).toMatch(/year/);
  });
});

describe('stringToColor', () => {
  it('returns a non-empty string for any input', () => {
    const result = stringToColor('hello');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('returns the same color for the same input', () => {
    expect(stringToColor('alice')).toBe(stringToColor('alice'));
  });

  it('returns different colors for different inputs', () => {
    // Not guaranteed for all pairs, but statistically very likely for distinct words
    const colors = ['alice', 'bob', 'carol', 'dave'].map(stringToColor);
    const unique = new Set(colors);
    expect(unique.size).toBeGreaterThan(1);
  });

  it('handles an empty string without throwing', () => {
    expect(() => stringToColor('')).not.toThrow();
  });
});

describe('delay', () => {
  it('resolves after the specified time', async () => {
    vi.useFakeTimers();
    const promise = delay(100);
    vi.advanceTimersByTime(100);
    await expect(promise).resolves.toBeUndefined();
    vi.useRealTimers();
  });

  it('does not resolve before the specified time', async () => {
    vi.useFakeTimers();
    let resolved = false;
    void delay(200).then(() => {
      resolved = true;
    });
    vi.advanceTimersByTime(100);
    expect(resolved).toBe(false);
    vi.advanceTimersByTime(100);
    await Promise.resolve(); // flush microtasks
    expect(resolved).toBe(true);
    vi.useRealTimers();
  });

  it('can be cancelled via the .cancel() method without rejecting by default', () => {
    vi.useFakeTimers();
    const d = delay(100);
    expect(() => d.cancel()).not.toThrow();
    vi.useRealTimers();
  });

  it('rejects on cancel when rejectOnCancel=true', async () => {
    vi.useFakeTimers();
    const d = delay(100, true);
    const rejection = expect(d).rejects.toBeUndefined();
    d.cancel();
    await rejection;
    vi.useRealTimers();
  });
});

describe('getProvider', () => {
  const originalLocation = window.location;

  afterEach(() => {
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
  });

  it('returns the provider from the search params when not in oauth path', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { pathname: '/login', search: '?provider=azure', href: 'http://localhost/login?provider=azure' }
    });
    expect(getProvider()).toBe('azure');
  });

  it('returns null when no provider param is present and path is not oauth', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { pathname: '/hits', search: '', href: 'http://localhost/hits' }
    });
    expect(getProvider()).toBeNull();
  });
});

describe('searchResultsDisplay', () => {
  const originalLocation = window.location;

  afterEach(() => {
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
  });

  it('returns count as string when below the max', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { pathname: '/', search: '', href: 'http://localhost/' }
    });
    expect(searchResultsDisplay(500)).toBe('500');
  });

  it('appends "+" when count equals the default max (10000) and no track_total_hits param', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { pathname: '/', search: '', href: 'http://localhost/' }
    });
    expect(searchResultsDisplay(10000)).toBe('10000+');
  });

  it('appends "+" when count matches the explicit track_total_hits param', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { pathname: '/', search: '?track_total_hits=500', href: 'http://localhost/?track_total_hits=500' }
    });
    expect(searchResultsDisplay(500)).toBe('500+');
  });

  it('does not append "+" when count does not equal track_total_hits', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { pathname: '/', search: '?track_total_hits=1000', href: 'http://localhost/?track_total_hits=1000' }
    });
    expect(searchResultsDisplay(500)).toBe('500');
  });

  it('uses a custom max when provided', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { pathname: '/', search: '', href: 'http://localhost/' }
    });
    expect(searchResultsDisplay(500, 500)).toBe('500+');
    expect(searchResultsDisplay(499, 500)).toBe('499');
  });
});
