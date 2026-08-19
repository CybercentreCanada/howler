import { describe, expect, it } from 'vitest';
import DossierGroupValidation from '../utils/DossierGroupValidation';

describe('DossierGroupValidation', () => {
  it('returns null for an empty string', () => {
    expect(DossierGroupValidation('')).toBeNull();
  });

  it('returns null for undefined/null-like input', () => {
    expect(DossierGroupValidation(undefined as unknown as string)).toBeNull();
    expect(DossierGroupValidation(null as unknown as string)).toBeNull();
  });

  it('returns null for a valid single-level group', () => {
    expect(DossierGroupValidation('network')).toBeNull();
  });

  it('returns null for a valid multi-level group', () => {
    expect(DossierGroupValidation('network/dns/query')).toBeNull();
  });

  it('accepts accented characters', () => {
    expect(DossierGroupValidation('réseauÙÛÜŸÀÂÆÇÉÈÊËÏÎÔŒ')).toBeNull();
  });

  it('rejects digits and other disallowed characters', () => {
    expect(DossierGroupValidation('network1')).toBe('route.pivots.groups.invalid.character');
    expect(DossierGroupValidation('network-dns')).toBe('route.pivots.groups.invalid.character');
    expect(DossierGroupValidation('network_dns')).toBe('route.pivots.groups.invalid.character');
  });

  it('rejects "pivot" as a whole path segment', () => {
    expect(DossierGroupValidation('pivot')).toBe('route.pivots.groups.invalid.word');
    expect(DossierGroupValidation('pivot/network')).toBe('route.pivots.groups.invalid.word');
    expect(DossierGroupValidation('network/pivot')).toBe('route.pivots.groups.invalid.word');
    expect(DossierGroupValidation('network/pivot/dns')).toBe('route.pivots.groups.invalid.word');
  });

  it('allows "pivot" as part of a longer segment', () => {
    expect(DossierGroupValidation('pivots')).toBeNull();
    expect(DossierGroupValidation('network/pivots')).toBeNull();
  });

  it('rejects consecutive slashes', () => {
    expect(DossierGroupValidation('network//dns')).toBe('route.pivots.groups.invalid.format');
  });

  it('rejects a leading slash', () => {
    expect(DossierGroupValidation('/network')).toBe('route.pivots.groups.invalid.format');
  });

  it('rejects a trailing slash', () => {
    expect(DossierGroupValidation('network/')).toBe('route.pivots.groups.invalid.format');
  });

  it('prioritizes the character check over the reserved word check', () => {
    expect(DossierGroupValidation('pivot1')).toBe('route.pivots.groups.invalid.character');
  });
});
