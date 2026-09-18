/// <reference types="vitest" />
import { afterEach, describe, expect, it, vi } from 'vitest';

const loadConstants = async (isoDate = '2024-01-02T03:15:00Z') => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(isoDate));
  vi.resetModules();
  return import('./constants');
};

afterEach(() => {
  vi.useRealTimers();
  vi.resetModules();
});

describe('constants', () => {
  it('builds prefixed storage keys for mock stores', async () => {
    const { MOCK_FAVOURITES_STORE, MOCK_SEARCH_QUERY_STORE, MY_LOCAL_STORAGE_PREFIX, StorageKey } = await loadConstants();

    expect(MOCK_SEARCH_QUERY_STORE).toBe(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.MOCK_SEARCH_QUERY_STORE}`);
    expect(MOCK_FAVOURITES_STORE).toBe(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.MOCK_FAVOURITES_STORE}`);
  });

  it('keeps storage key values stable for persisted UI state', async () => {
    const { StorageKey } = await loadConstants();

    expect(StorageKey.APP_TOKEN).toBe('app_token');
    expect(StorageKey.ETAG).toBe('etag');
    expect(StorageKey.LOGIN_NONCE).toBe('login_nonce');
    expect(StorageKey.DISPLAY_TYPE).toBe('display_type');
  });

  it('computes the staggered rule intervals from the current time', async () => {
    const { RULE_INTERVALS, hours, minutes } = await loadConstants();

    expect(minutes).toEqual([15, 45]);
    expect(hours).toEqual([0, 3, 6, 9, 12, 15, 18, 21]);
    expect(RULE_INTERVALS).toEqual([
      { key: 'rule.interval.thirty.minutes', crontab: '15,45 * * * *' },
      { key: 'rule.interval.one.hour', crontab: '15 * * * *' },
      { key: 'rule.interval.three.hours', crontab: '15 0,3,6,9,12,15,18,21 * * *' },
      { key: 'rule.interval.six.hours', crontab: '15 3,9,15,21 * * *' },
      { key: 'rule.interval.one.day', crontab: '15 3 * * *' }
    ]);
  });

  it('exports the supported date range presets and Lucene mappings', async () => {
    const { DATE_RANGES, DATE_RANGE_LUCENE } = await loadConstants();

    expect(DATE_RANGES).toEqual([
      'date.range.1.day',
      'date.range.3.day',
      'date.range.1.week',
      'date.range.1.month',
      'date.range.all',
      'date.range.custom'
    ]);
    expect(DATE_RANGE_LUCENE).toEqual({
      'date.range.1.day': 'now-1d/d',
      'date.range.3.day': 'now-3d/d',
      'date.range.1.week': 'now-7d/d',
      'date.range.1.month': 'now-1M/M'
    });
  });

  it('exposes configured label metadata for known label types', async () => {
    const { LABEL_TYPES, VALID_ACTION_TRIGGERS, DEFAULT_QUERY } = await loadConstants();

    expect(VALID_ACTION_TRIGGERS).toEqual(['create', 'promote', 'demote']);
    expect(DEFAULT_QUERY).toBe('howler.id:*');
    expect(LABEL_TYPES.insight.icon?.props.fontSize).toBe('small');
    expect(LABEL_TYPES.operation.color).toBeDefined();
    expect(LABEL_TYPES.generic).toEqual({});
  });
});
