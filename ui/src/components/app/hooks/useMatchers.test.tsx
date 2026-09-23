/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockGetRecord = vi.hoisted(() => vi.fn());

vi.mock('use-context-selector', async importOriginal => {
  const actual = await importOriginal<typeof import('use-context-selector')>();
  return {
    ...actual,
    useContextSelector: (_context: unknown, selector: (ctx: any) => any) => selector({ getRecord: mockGetRecord })
  };
});

import useMatchers from './useMatchers';

describe('useMatchers', () => {
  it('prefers provided metadata over fallback lookups', async () => {
    const hit = {
      howler: { id: 'hit-1' },
      __template: { id: 'template-1' },
      __overview: { id: 'overview-1' },
      __dossiers: [{ id: 'dossier-1' }],
      __analytic: { id: 'analytic-1' }
    } as any;

    const { result } = renderHook(() => useMatchers());

    await expect(result.current.getMatchingTemplate(hit, { id: 'template-override' } as any)).resolves.toEqual({
      id: 'template-override'
    });
    await expect(result.current.getMatchingTemplate(hit)).resolves.toEqual({ id: 'template-1' });
    await expect(result.current.getMatchingOverview(hit)).resolves.toEqual({ id: 'overview-1' });
    await expect(result.current.getMatchingDossiers(hit)).resolves.toEqual([{ id: 'dossier-1' }]);
    await expect(result.current.getMatchingAnalytic(hit)).resolves.toEqual({ id: 'analytic-1' });
    expect(mockGetRecord).not.toHaveBeenCalled();
  });

  it('falls back to fetching a record unless lazy mode is enabled', async () => {
    mockGetRecord.mockResolvedValue({
      __template: { id: 'template-fetched' },
      __overview: { id: 'overview-fetched' },
      __dossiers: [{ id: 'dossier-fetched' }],
      __analytic: { id: 'analytic-fetched' }
    });

    const hit = { howler: { id: 'hit-2' } } as any;
    const eager = renderHook(() => useMatchers());

    await expect(eager.result.current.getMatchingTemplate(hit)).resolves.toEqual({ id: 'template-fetched' });
    await expect(eager.result.current.getMatchingOverview(hit)).resolves.toEqual({ id: 'overview-fetched' });
    await expect(eager.result.current.getMatchingDossiers(hit)).resolves.toEqual([{ id: 'dossier-fetched' }]);
    await expect(eager.result.current.getMatchingAnalytic(hit)).resolves.toEqual({ id: 'analytic-fetched' });

    const lazy = renderHook(() => useMatchers(true));
    await expect(lazy.result.current.getMatchingTemplate(hit)).resolves.toBeUndefined();
    await expect(lazy.result.current.getMatchingOverview(hit)).resolves.toBeUndefined();
    await expect(lazy.result.current.getMatchingDossiers(hit)).resolves.toEqual([]);
    await expect(lazy.result.current.getMatchingAnalytic(hit)).resolves.toBeUndefined();
  });

  it('handles missing hits and fetch failures gracefully', async () => {
    mockGetRecord.mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useMatchers());
    const hit = { howler: { id: 'hit-3' } } as any;

    await expect(result.current.getMatchingTemplate(undefined as any)).resolves.toBeUndefined();
    await expect(result.current.getMatchingOverview(undefined as any)).resolves.toBeUndefined();
    await expect(result.current.getMatchingDossiers(undefined as any)).resolves.toEqual([]);
    await expect(result.current.getMatchingAnalytic(undefined as any)).resolves.toBeUndefined();

    await expect(result.current.getMatchingTemplate(hit)).resolves.toBeUndefined();
    await expect(result.current.getMatchingOverview(hit)).resolves.toBeUndefined();
    await expect(result.current.getMatchingDossiers(hit)).resolves.toEqual([]);
    await expect(result.current.getMatchingAnalytic(hit)).resolves.toBeUndefined();
  });
});
