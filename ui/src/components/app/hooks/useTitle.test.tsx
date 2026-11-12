/// <reference types="vitest" />
import { renderHook, waitFor } from '@testing-library/react';
import type { Event } from 'models/entities/generated/Event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const analyticContextToken = vi.hoisted(() => ({ name: 'analytic-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));

let locationValue = { pathname: '/', search: '' };
let paramsValue: any = {};
let searchParamsValue = new URLSearchParams();
let breadcrumbsValue: any[] = [];
let analyticContextValue: any = {};
let recordValue: any = { records: {}, getRecord: vi.fn() };

vi.mock('@tui/core', () => ({
  useAppRouter: () => ({ breadcrumbs: () => breadcrumbsValue })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => `translated:${key}` })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue,
  useParams: () => paramsValue,
  useSearchParams: () => [searchParamsValue]
}));

vi.mock('../providers/AnalyticProvider', () => ({
  AnalyticContext: analyticContextToken
}));

vi.mock('../providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('use-context-selector', async importOriginal => {
  const actual = await importOriginal<typeof import('use-context-selector')>();
  return {
    ...actual,
    useContextSelector: (_context: any, selector: (ctx: any) => any) => selector(recordValue)
  };
});

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === analyticContextToken) {
        return analyticContextValue;
      }
      return actual.useContext(context);
    }
  };
});

import useTitle from './useTitle';

describe('useTitle', () => {
  beforeEach(() => {
    document.head.innerHTML = '<title></title>';
    locationValue = { pathname: '/', search: '' };
    paramsValue = {};
    searchParamsValue = new URLSearchParams();
    breadcrumbsValue = [];
    analyticContextValue = {};
    recordValue = { records: {}, getRecord: vi.fn() };
  });

  it('sets analytic titles from ids or falls back to the section title', async () => {
    locationValue = { pathname: '/analytics/123', search: '' };
    paramsValue = { id: '123' };
    analyticContextValue = { getAnalyticFromId: vi.fn().mockResolvedValue({ name: 'Suspicious Login' }) };

    renderHook(() => useTitle());
    await waitFor(() => expect(document.title).toBe('translated:route.analytics.view - Suspicious Login'));

    analyticContextValue = { getAnalyticFromId: vi.fn().mockResolvedValue(undefined) };
    renderHook(() => useTitle());
    await waitFor(() => expect(document.title).toBe('translated:route.analytics.view'));

    locationValue = { pathname: '/analytics', search: '' };
    paramsValue = {};
    renderHook(() => useTitle());
    await waitFor(() => expect(document.title).toBe('Howler - translated:route.analytics'));
  });

  it('sets hit titles from cached or fetched records', async () => {
    locationValue = { pathname: '/hits/h1', search: '' };
    paramsValue = { id: 'h1' };
    recordValue = {
      records: {
        h1: { __index: 'hit', howler: { escalation: 'alert', analytic: 'One', detection: 'Two' } }
      },
      getRecord: vi.fn()
    };

    renderHook(() => useTitle());
    await waitFor(() => expect(document.title).toBe('Alert - One: Two'));

    recordValue = {
      records: {},
      getRecord: vi.fn().mockResolvedValue({ __index: 'hit', howler: { escalation: 'hit', analytic: 'Three' } })
    };
    paramsValue = { id: 'h2' };
    renderHook(() => useTitle());
    await waitFor(() => expect(document.title).toBe('Hit - Three'));
  });

  it('sets template and breadcrumb titles', async () => {
    locationValue = { pathname: '/templates/view', search: '?analytic=Demo&detection=X' };
    searchParamsValue = new URLSearchParams('analytic=Demo&detection=X');

    renderHook(() => useTitle());
    await waitFor(() => expect(document.title).toBe('translated:route.templates.view - Demo: X'));

    locationValue = { pathname: '/views', search: '' };
    searchParamsValue = new URLSearchParams();
    breadcrumbsValue = [{ i18nKey: 'route.views' }];
    renderHook(() => useTitle());
    await waitFor(() => expect(document.title).toBe('Howler - translated:route.views'));
  });

  it.each([
    { message: 'VPN activity', provider: 'collector', label: 'VPN activity' },
    { message: '', provider: 'collector', label: 'collector' },
    { message: '', provider: undefined, label: 'event-1' }
  ])(
    'uses the event message, provider, or id for cached event titles: $label',
    async ({ message, provider, label }) => {
      const event: Event = {
        __index: 'event',
        timestamp: '2026-01-01T00:00:00Z',
        message,
        event: { provider },
        howler: { id: 'event-1', hash: 'abc' }
      };
      locationValue = { pathname: '/events/event-1', search: '' };
      paramsValue = { id: 'event-1' };
      recordValue = { records: { 'event-1': event }, getRecord: vi.fn() };

      renderHook(() => useTitle());

      await waitFor(() => expect(document.title).toBe(`translated:page.cases.observables.origin.event - ${label}`));
      expect(recordValue.getRecord).not.toHaveBeenCalled();
    }
  );

  it('narrows a fetched event even when it is requested from a hit route', async () => {
    const event: Event = {
      __index: 'event',
      timestamp: '2026-01-01T00:00:00Z',
      howler: { id: 'event-2', hash: 'abc' }
    };
    locationValue = { pathname: '/hits/event-2', search: '' };
    paramsValue = { id: 'event-2' };
    recordValue = { records: {}, getRecord: vi.fn().mockResolvedValue(event) };

    renderHook(() => useTitle());

    await waitFor(() => expect(document.title).toBe('translated:page.cases.observables.origin.event - event-2'));
    expect(recordValue.getRecord).toHaveBeenCalledWith('event-2');
  });
});
