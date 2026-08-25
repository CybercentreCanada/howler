import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import { describe, expect, it } from 'vitest';
import pivotForest from '../utils/pivotForest';

const makePivot = (overrides: Partial<Pivot> = {}): Pivot =>
  ({
    value: 'value',
    ...overrides
  }) as unknown as Pivot;

const makeDossier = (pivots?: Pivot[]): Dossier =>
  ({
    pivots
  }) as unknown as Dossier;

describe('pivotForest', () => {
  it('returns an empty forest when there are no dossiers', () => {
    expect(pivotForest([])).toEqual([]);
  });

  it('skips dossiers without pivots', () => {
    expect(pivotForest([makeDossier(undefined)])).toEqual([]);
  });

  it('returns ungrouped pivots as a single root node with an empty path', () => {
    const pivot = makePivot({ value: 'ungrouped' });
    const dossier = makeDossier([pivot]);
    expect(pivotForest([dossier])).toEqual([{ path: '', pivots: [{ pivot, dossier }], children: [] }]);
  });

  it('treats an empty string group the same as no group', () => {
    const pivot = makePivot({ group: '' });
    const dossier = makeDossier([pivot]);
    expect(pivotForest([dossier])).toEqual([{ path: '', pivots: [{ pivot, dossier }], children: [] }]);
  });

  it('returns a node for a single-level group', () => {
    const pivot = makePivot({ group: 'network' });
    const dossier = makeDossier([pivot]);
    expect(pivotForest([dossier])).toEqual([{ path: 'network', pivots: [{ pivot, dossier }], children: [] }]);
  });

  it('collapses an unbranched multi-level group path into a single node', () => {
    const pivot = makePivot({ group: 'network/dns/query' });
    const dossier = makeDossier([pivot]);
    expect(pivotForest([dossier])).toEqual([{ path: 'network/dns/query', pivots: [{ pivot, dossier }], children: [] }]);
  });

  it('collapses repeated segment names the same as any other unbranched chain', () => {
    const pivot = makePivot({ group: 'test/test' });
    const dossier = makeDossier([pivot]);
    expect(pivotForest([dossier])).toEqual([{ path: 'test/test', pivots: [{ pivot, dossier }], children: [] }]);
  });

  it('keeps all pivots sharing the same group on the same node', () => {
    const pivotA = makePivot({ value: 'a', group: 'network' });
    const pivotB = makePivot({ value: 'b', group: 'network' });
    const dossierA = makeDossier([pivotA]);
    const dossierB = makeDossier([pivotB]);
    expect(pivotForest([dossierA, dossierB])).toEqual([
      {
        path: 'network',
        pivots: [
          { pivot: pivotA, dossier: dossierA },
          { pivot: pivotB, dossier: dossierB }
        ],
        children: []
      }
    ]);
  });

  it('keeps grouped and ungrouped pivots from the same dossier as separate nodes', () => {
    const grouped = makePivot({ value: 'grouped', group: 'network' });
    const ungrouped = makePivot({ value: 'ungrouped' });
    const dossier = makeDossier([grouped, ungrouped]);
    expect(pivotForest([dossier])).toEqual([
      { path: '', pivots: [{ pivot: ungrouped, dossier }], children: [] },
      { path: 'network', pivots: [{ pivot: grouped, dossier }], children: [] }
    ]);
  });

  it('branches sibling groups into children', () => {
    const dnsPivot = makePivot({ value: 'dns', group: 'network/dns' });
    const httpPivot = makePivot({ value: 'http', group: 'network/http' });
    const dossier = makeDossier([dnsPivot, httpPivot]);
    expect(pivotForest([dossier])).toEqual([
      {
        path: 'network',
        pivots: [],
        children: [
          { path: 'dns', pivots: [{ pivot: dnsPivot, dossier }], children: [] },
          { path: 'http', pivots: [{ pivot: httpPivot, dossier }], children: [] }
        ]
      }
    ]);
  });

  it('keeps a branch point as its own node but still collapses each unbranched chain below it', () => {
    const v4Pivot = makePivot({ value: 'v4', group: 'network/ip/v4/local' });
    const v6Pivot = makePivot({ value: 'v6', group: 'network/ip/v6/local' });
    const dossier = makeDossier([v4Pivot, v6Pivot]);
    expect(pivotForest([dossier])).toEqual([
      {
        path: 'network/ip',
        pivots: [],
        children: [
          { path: 'v4/local', pivots: [{ pivot: v4Pivot, dossier }], children: [] },
          { path: 'v6/local', pivots: [{ pivot: v6Pivot, dossier }], children: [] }
        ]
      }
    ]);
  });

  it('returns a node for each distinct top-level group, without merging them together', () => {
    const networkPivot = makePivot({ value: 'network', group: 'network' });
    const systemPivot = makePivot({ value: 'system', group: 'system' });
    const dossier = makeDossier([networkPivot, systemPivot]);
    expect(pivotForest([dossier])).toEqual([
      { path: 'network', pivots: [{ pivot: networkPivot, dossier }], children: [] },
      { path: 'system', pivots: [{ pivot: systemPivot, dossier }], children: [] }
    ]);
  });

  it('keeps a group own pivots alongside a nested child branch, without collapsing', () => {
    const parentPivot = makePivot({ value: 'parent', group: 'network' });
    const childPivot = makePivot({ value: 'child', group: 'network/dns' });
    const dossier = makeDossier([parentPivot, childPivot]);
    expect(pivotForest([dossier])).toEqual([
      {
        path: 'network',
        pivots: [{ pivot: parentPivot, dossier }],
        children: [{ path: 'dns', pivots: [{ pivot: childPivot, dossier }], children: [] }]
      }
    ]);
  });
});
