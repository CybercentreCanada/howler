import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import { describe, expect, it, vi } from 'vitest';
import { resolvePivotUrl } from './utils';

const hit = {
  event: { domains: ['first.example', 'second.example'] },
  user: { name: 'alice' }
} as unknown as Hit;

describe('resolvePivotUrl', () => {
  it('resolves custom, hit, array, and helper mappings', () => {
    const helper = {
      keyword: 'upper',
      callback: (value: string) => value.toUpperCase()
    };
    const pivot = {
      value: '{{domain}}/{{custom}}/{{upper user}}',
      mappings: [
        { key: 'domain', field: 'event.domains' },
        { key: 'custom', field: 'custom', custom_value: 'fixed' },
        { key: 'user', field: 'user.name' }
      ]
    } as Pivot;

    expect(resolvePivotUrl(pivot, hit, [helper])).toBe('first.example/fixed/ALICE');
  });

  it('returns the original template when handlebars compilation fails', () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const pivot = { value: '{{#if', mappings: [] } as Pivot;

    expect(resolvePivotUrl(pivot)).toBe('{{#if');
    expect(error).toHaveBeenCalledOnce();
    error.mockRestore();
  });
});
