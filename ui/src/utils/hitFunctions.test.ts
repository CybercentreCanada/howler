/// <reference types="vitest" />
import type { Hit } from 'models/entities/generated/Hit';
import { describe, expect, it } from 'vitest';
import { getUserList } from './hitFunctions';

const makeHit = (howlerOverrides: Partial<NonNullable<Hit['howler']>> = {}): Hit =>
  ({
    howler: {
      log: [],
      comment: [],
      ...howlerOverrides
    }
  }) as unknown as Hit;

describe('getUserList', () => {
  it('returns an empty Set when the hit is null', () => {
    expect(getUserList(null as any)).toEqual(new Set());
  });

  it('returns an empty Set when the hit is undefined', () => {
    expect(getUserList(undefined as any)).toEqual(new Set());
  });

  it('returns an empty Set when both log and comment are empty', () => {
    expect(getUserList(makeHit())).toEqual(new Set());
  });

  it('collects users from the log array', () => {
    const hit = makeHit({ log: [{ user: 'alice' }, { user: 'bob' }] as any });
    expect(getUserList(hit)).toEqual(new Set(['alice', 'bob']));
  });

  it('collects users from the comment array', () => {
    const hit = makeHit({ comment: [{ user: 'carol' }] as any });
    expect(getUserList(hit)).toEqual(new Set(['carol']));
  });

  it('collects users from both log and comment', () => {
    const hit = makeHit({
      log: [{ user: 'alice' }] as any,
      comment: [{ user: 'bob' }] as any
    });
    expect(getUserList(hit)).toEqual(new Set(['alice', 'bob']));
  });

  it('deduplicates users that appear in both arrays', () => {
    const hit = makeHit({
      log: [{ user: 'alice' }] as any,
      comment: [{ user: 'alice' }] as any
    });
    const result = getUserList(hit);
    expect(result).toEqual(new Set(['alice']));
    expect(result.size).toBe(1);
  });

  it('deduplicates users that appear multiple times in the same array', () => {
    const hit = makeHit({ log: [{ user: 'alice' }, { user: 'alice' }] as any });
    expect(getUserList(hit).size).toBe(1);
  });

  it('handles a hit with no howler field gracefully', () => {
    const hit = {} as Hit;
    expect(getUserList(hit)).toEqual(new Set());
  });
});
