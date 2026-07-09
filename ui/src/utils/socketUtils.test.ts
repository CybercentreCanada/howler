import { describe, expect, it } from 'vitest';
import { isHitUpdate } from './socketUtils';

describe('isHitUpdate', () => {
  it('returns truthy when data has both a truthy version and a hit', () => {
    expect(isHitUpdate({ version: 1, hit: {} })).toBeTruthy();
  });

  it('returns truthy when version is a non-empty string', () => {
    expect(isHitUpdate({ version: 'v1', hit: { howler: {} } })).toBeTruthy();
  });

  it('returns falsy when version is missing', () => {
    expect(isHitUpdate({ hit: {} })).toBeFalsy();
  });

  it('returns falsy when hit is missing', () => {
    expect(isHitUpdate({ version: 1 })).toBeFalsy();
  });

  it('returns falsy when both fields are missing', () => {
    expect(isHitUpdate({})).toBeFalsy();
  });

  it('returns falsy when version is 0 (falsy)', () => {
    expect(isHitUpdate({ version: 0, hit: {} })).toBeFalsy();
  });

  it('returns falsy when hit is null (falsy)', () => {
    expect(isHitUpdate({ version: 1, hit: null })).toBeFalsy();
  });
});
