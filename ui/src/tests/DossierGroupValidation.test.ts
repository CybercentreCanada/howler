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

  it('accepts digits but still rejects other disallowed characters', () => {
    expect(DossierGroupValidation('network1')).toBeNull();
    expect(DossierGroupValidation('net2work')).toBeNull();
    expect(DossierGroupValidation('network/zone2')).toBeNull();
    expect(DossierGroupValidation('network-dns')).toBe('route.dossiers.pivots.invalid.character');
    expect(DossierGroupValidation('network_dns')).toBe('route.dossiers.pivots.invalid.character');
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

  it('allows reserved word variants that are not exact segment matches', () => {
    expect(DossierGroupValidation('pivot1')).toBeNull();
  });
});
