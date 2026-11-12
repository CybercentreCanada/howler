import { renderHook } from '@testing-library/react';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { APIConfiguration } from 'models/entities/generated/ApiType';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import type { PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useType } from './utils';

const guessType = vi.hoisted(() => vi.fn<(value: string) => string | null>());
vi.mock('@cccsaurora/clue-ui', () => ({
  useClueEnrichSelector: (selector: (ctx: { guessType: typeof guessType }) => typeof guessType) =>
    selector({ guessType })
}));

let mapping: Record<string, string> = {};
const Wrapper = ({ children }: PropsWithChildren) => {
  const configuration: APIConfiguration = {
    auth: { allow_apikeys: true, allow_extended_apikeys: false, oauth_providers: [], internal: { enabled: true } },
    system: {
      type: 'test',
      version: 'test',
      branch: 'test',
      commit: 'test',
      retention: { enabled: false, limit_unit: 'days', limit_amount: 1 }
    },
    ui: { apps: [] },
    features: { clue: true, notebook: false },
    clue: { status_checks: [] },
    mapping
  };
  return (
    <ApiConfigContext.Provider value={{ config: { configuration }, setConfig: vi.fn(), loaded: true }}>
      {children}
    </ApiConfigContext.Provider>
  );
};

const event: Event = {
  __index: 'event',
  timestamp: '2026-01-01T00:00:00Z',
  howler: { id: 'event-1', hash: 'abc' }
};

describe('useType', () => {
  beforeEach(() => {
    mapping = {};
    guessType.mockReset().mockReturnValue(null);
  });

  it('preserves hit Clue overrides ahead of configuration and guessing', () => {
    const hit: Hit = {
      __index: 'hit',
      timestamp: '2026-01-01T00:00:00Z',
      howler: { id: 'hit-1', hash: 'abc', analytic: 'Analytic', assignment: 'unassigned' },
      clue: { types: [{ field: 'destination.ip', type: 'custom-ip' }] }
    };
    mapping = { 'destination.ip': 'ip' };
    const { result } = renderHook(() => useType(hit, 'destination.ip', '192.0.2.1'), { wrapper: Wrapper });

    expect(result.current).toBe('custom-ip');
    expect(guessType).not.toHaveBeenCalled();
  });

  it('uses configuration for an event without a Clue extension', () => {
    mapping = { 'destination.ip': 'ip' };
    const { result } = renderHook(() => useType(event, 'destination.ip', '192.0.2.1'), { wrapper: Wrapper });

    expect(result.current).toBe('ip');
    expect(guessType).not.toHaveBeenCalled();
  });

  it('guesses an event value when configuration has no mapping', () => {
    guessType.mockReturnValue('domain');
    const { result } = renderHook(() => useType(event, 'destination.address', 'example.test'), { wrapper: Wrapper });

    expect(result.current).toBe('domain');
    expect(guessType).toHaveBeenCalledWith('example.test');
  });

  it('returns null for an event without a mapping or value', () => {
    const { result } = renderHook(() => useType(event), { wrapper: Wrapper });

    expect(result.current).toBeNull();
    expect(guessType).not.toHaveBeenCalled();
  });
});
