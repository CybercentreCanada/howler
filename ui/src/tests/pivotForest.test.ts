import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import { describe, expect, it } from 'vitest';
import pivotForest from '../utils/PivotGrouping';

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
    expect(pivotForest([makeDossier([pivot])])).toEqual([{ path: '', pivots: [pivot], children: [] }]);
  });

  it('treats an empty string group the same as no group', () => {
    const pivot = makePivot({ group: '' });
    expect(pivotForest([makeDossier([pivot])])).toEqual([{ path: '', pivots: [pivot], children: [] }]);
  });

  it('returns a node for a single-level group without collapsing the "pivot" key into the path', () => {
    const pivot = makePivot({ group: 'network' });
    expect(pivotForest([makeDossier([pivot])])).toEqual([{ path: 'network', pivots: [pivot], children: [] }]);
  });

  it('collapses a multi-level group path with no branching into a single node', () => {
    const pivot = makePivot({ group: 'network/dns/query' });
    expect(pivotForest([makeDossier([pivot])])).toEqual([{ path: 'network/dns/query', pivots: [pivot], children: [] }]);
  });

  it('keeps all pivots sharing the same group on the same node', () => {
    const pivotA = makePivot({ value: 'a', group: 'network' });
    const pivotB = makePivot({ value: 'b', group: 'network' });
    expect(pivotForest([makeDossier([pivotA]), makeDossier([pivotB])])).toEqual([
      { path: 'network', pivots: [pivotA, pivotB], children: [] }
    ]);
  });

  it('keeps grouped and ungrouped pivots from the same dossier as separate nodes', () => {
    const grouped = makePivot({ value: 'grouped', group: 'network' });
    const ungrouped = makePivot({ value: 'ungrouped' });
    expect(pivotForest([makeDossier([grouped, ungrouped])])).toEqual([
      { path: '', pivots: [ungrouped], children: [] },
      { path: 'network', pivots: [grouped], children: [] }
    ]);
  });

  it('branches sibling groups into children instead of collapsing when there is more than one path', () => {
    const dnsPivot = makePivot({ value: 'dns', group: 'network/dns' });
    const httpPivot = makePivot({ value: 'http', group: 'network/http' });
    expect(pivotForest([makeDossier([dnsPivot, httpPivot])])).toEqual([
      {
        path: 'network',
        pivots: [],
        children: [
          { path: 'dns', pivots: [dnsPivot], children: [] },
          { path: 'http', pivots: [httpPivot], children: [] }
        ]
      }
    ]);
  });

  it('returns a node for each distinct top-level group, in insertion order', () => {
    const networkPivot = makePivot({ value: 'network', group: 'network' });
    const systemPivot = makePivot({ value: 'system', group: 'system' });
    expect(pivotForest([makeDossier([networkPivot, systemPivot])])).toEqual([
      { path: 'network', pivots: [networkPivot], children: [] },
      { path: 'system', pivots: [systemPivot], children: [] }
    ]);
  });

  it('keeps a group own pivots alongside a nested child branch, without collapsing', () => {
    const parentPivot = makePivot({ value: 'parent', group: 'network' });
    const childPivot = makePivot({ value: 'child', group: 'network/dns' });
    expect(pivotForest([makeDossier([parentPivot, childPivot])])).toEqual([
      {
        path: 'network',
        pivots: [parentPivot],
        children: [{ path: 'dns', pivots: [childPivot], children: [] }]
      }
    ]);
  });
});
