import type { View } from 'models/entities/generated/View';
import { describe, expect, it } from 'vitest';
import { buildViewUrl } from './viewUtils';

const makeView = (overrides: Partial<View> = {}): View => ({
  view_id: 'view-1',
  title: 'Test View',
  query: 'howler.status:open',
  sort: 'event.created desc',
  span: 'date.range.1.month',
  type: 'personal',
  owner: 'testuser',
  ...overrides
});

describe('buildViewUrl', () => {
  it('includes the view_id as the "view" query param', () => {
    const url = buildViewUrl(makeView({ view_id: 'abc-123' }));
    expect(url).toContain('view=abc-123');
  });

  it('starts with /search', () => {
    const url = buildViewUrl(makeView());
    expect(url.startsWith('/search?')).toBe(true);
  });

  it('includes the span param when provided', () => {
    const url = buildViewUrl(makeView({ span: 'date.range.1.week' }));
    expect(url).toContain('span=date.range.1.week');
  });

  it('omits the span param when span is undefined', () => {
    const url = buildViewUrl(makeView({ span: undefined }));
    expect(url).not.toContain('span=');
  });

  it('includes the sort param when provided', () => {
    const url = buildViewUrl(makeView({ sort: 'event.created asc' }));
    expect(url).toContain('sort=event.created+asc');
  });

  it('omits the sort param when sort is undefined', () => {
    const url = buildViewUrl(makeView({ sort: undefined }));
    expect(url).not.toContain('sort=');
  });

  it('builds a complete URL with all fields present', () => {
    const url = buildViewUrl(makeView({ view_id: 'v1', span: 'date.range.1.day', sort: 'event.created desc' }));
    const parsed = new URL(url, 'http://localhost');
    expect(parsed.searchParams.get('view')).toBe('v1');
    expect(parsed.searchParams.get('span')).toBe('date.range.1.day');
    expect(parsed.searchParams.get('sort')).toBe('event.created desc');
  });
});
