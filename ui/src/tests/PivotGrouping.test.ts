import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import { describe, expect, it } from 'vitest';
import pivotGrouping from '../utils/PivotGrouping';

const makePivot = (overrides: Partial<Pivot> = {}): Pivot =>
  ({
    value: 'value',
    ...overrides
  }) as unknown as Pivot;

const makeDossier = (pivots?: Pivot[]): Dossier =>
  ({
    pivots
  }) as unknown as Dossier;

describe('pivotGrouping', () => {
  it('returns an empty tree when there are no dossiers', () => {
    expect(pivotGrouping([])).toEqual({});
  });

  it('skips dossiers without pivots', () => {
    expect(pivotGrouping([makeDossier(undefined)])).toEqual({});
  });

  it('puts ungrouped pivots directly at the root', () => {
    const pivot = makePivot({ value: 'ungrouped' });
    expect(pivotGrouping([makeDossier([pivot])])).toEqual({ pivot: [pivot] });
  });

  it('treats an empty string group the same as no group', () => {
    const pivot = makePivot({ group: '' });
    expect(pivotGrouping([makeDossier([pivot])])).toEqual({ pivot: [pivot] });
  });

  it('nests a pivot under a single-level group', () => {
    const pivot = makePivot({ group: 'network' });
    expect(pivotGrouping([makeDossier([pivot])])).toEqual({
      network: { pivot: [pivot] }
    });
  });

  it('nests a pivot under a multi-level group path', () => {
    const pivot = makePivot({ group: 'network/dns/query' });
    expect(pivotGrouping([makeDossier([pivot])])).toEqual({
      network: { dns: { query: { pivot: [pivot] } } }
    });
  });

  it('merges pivots from multiple dossiers into the same group', () => {
    const pivotA = makePivot({ value: 'a', group: 'network' });
    const pivotB = makePivot({ value: 'b', group: 'network' });
    expect(pivotGrouping([makeDossier([pivotA]), makeDossier([pivotB])])).toEqual({
      network: { pivot: [pivotA, pivotB] }
    });
  });

  it('keeps grouped and ungrouped pivots from the same dossier separate', () => {
    const grouped = makePivot({ value: 'grouped', group: 'network' });
    const ungrouped = makePivot({ value: 'ungrouped' });
    expect(pivotGrouping([makeDossier([grouped, ungrouped])])).toEqual({
      pivot: [ungrouped],
      network: { pivot: [grouped] }
    });
  });

  it('branches sibling groups that share a common ancestor', () => {
    const dnsPivot = makePivot({ value: 'dns', group: 'network/dns' });
    const httpPivot = makePivot({ value: 'http', group: 'network/http' });
    expect(pivotGrouping([makeDossier([dnsPivot, httpPivot])])).toEqual({
      network: {
        dns: { pivot: [dnsPivot] },
        http: { pivot: [httpPivot] }
      }
    });
  });
});
