import { describe, expect, it } from 'vitest';
import pivotGroupValidation from '../utils/pivotGroupValidation';

describe('pivotGroupValidation', () => {
  it('returns null for an empty string', () => {
    expect(pivotGroupValidation('')).toBeNull();
  });

  it('returns null for undefined/null-like input', () => {
    expect(pivotGroupValidation(undefined as unknown as string)).toBeNull();
    expect(pivotGroupValidation(null as unknown as string)).toBeNull();
  });

  it('returns null for a valid single-level group', () => {
    expect(pivotGroupValidation('network')).toBeNull();
  });

  it('returns null for a valid multi-level group', () => {
    expect(pivotGroupValidation('network/dns/query')).toBeNull();
  });

  it('accepts accented characters', () => {
    expect(pivotGroupValidation('réseauÙÛÜŸÀÂÆÇÉÈÊËÏÎÔŒ')).toBeNull();
  });

  it('accepts digits but still rejects other disallowed characters', () => {
    expect(pivotGroupValidation('0')).toBeNull();
    expect(pivotGroupValidation('network1')).toBeNull();
    expect(pivotGroupValidation('net2work')).toBeNull();
    expect(pivotGroupValidation('network/zone2')).toBeNull();
    expect(pivotGroupValidation('network-dns')).toBe('route.dossiers.pivots.invalid.character');
    expect(pivotGroupValidation('network_dns')).toBe('route.dossiers.pivots.invalid.character');
  });

  it('rejects "pivot" as a whole path segment', () => {
    expect(pivotGroupValidation('pivot')).toBe('route.pivots.groups.invalid.word');
    expect(pivotGroupValidation('pivot/network')).toBe('route.pivots.groups.invalid.word');
    expect(pivotGroupValidation('network/pivot')).toBe('route.pivots.groups.invalid.word');
    expect(pivotGroupValidation('network/pivot/dns')).toBe('route.pivots.groups.invalid.word');
  });

  it('allows "pivot" as part of a longer segment', () => {
    expect(pivotGroupValidation('pivots')).toBeNull();
    expect(pivotGroupValidation('network/pivots')).toBeNull();
  });

  it('rejects consecutive slashes', () => {
    expect(pivotGroupValidation('network//dns')).toBe('route.pivots.groups.invalid.format');
  });

  it('rejects a leading slash', () => {
    expect(pivotGroupValidation('/network')).toBe('route.pivots.groups.invalid.format');
  });

  it('rejects a trailing slash', () => {
    expect(pivotGroupValidation('network/')).toBe('route.pivots.groups.invalid.format');
  });

  it('allows reserved word variants that are not exact segment matches', () => {
    expect(pivotGroupValidation('pivot1')).toBeNull();
  });
});
