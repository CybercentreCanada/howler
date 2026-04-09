import type { Item } from 'models/entities/generated/Item';
import { describe, expect, it } from 'vitest';
import { buildTree } from './utils';

const hit = (path: string, value = path): Item => ({ type: 'hit', value, path });

describe('buildTree', () => {
  it('returns an empty tree for no items', () => {
    expect(buildTree()).toEqual({ path: '', leaves: [] });
  });

  it('returns an empty tree for an empty array', () => {
    expect(buildTree([])).toEqual({ path: '', leaves: [] });
  });

  it('ignores items with no path', () => {
    const noPath: Item = { type: 'hit', value: 'x' };
    expect(buildTree([noPath])).toEqual({ path: '', leaves: [] });
  });

  it('places a path-less item alongside a valid one without affecting the folder', () => {
    const valid = hit('folder/item');
    const noPath: Item = { type: 'hit', value: 'x' };
    const result = buildTree([valid, noPath]);
    expect(result.leaves).toEqual([]);
    expect(result.folders?.folder.leaves).toEqual([valid]);
  });

  it('places an item with a filename but no folder as a top-level leaf', () => {
    const flat = hit('flat-item');
    const result = buildTree([flat]);
    expect(result.leaves).toEqual([flat]);
    expect(result.folders).toBeUndefined();
  });

  it('places an item in a single-level folder', () => {
    const nested = hit('folderA/item');
    const result = buildTree([nested]);
    expect(result.leaves).toEqual([]);
    expect(result.folders?.folderA).toMatchObject({ path: 'folderA', leaves: [nested] });
  });

  it('sets path correctly for a single-level folder', () => {
    const result = buildTree([hit('folderA/item')]);
    expect(result.folders?.folderA.path).toBe('folderA');
  });

  it('places an item in a two-level nested folder', () => {
    const deep = hit('a/b/item');
    const result = buildTree([deep]);
    expect(result.folders?.a.folders?.b.leaves).toEqual([deep]);
  });

  it('sets path correctly for deeply nested folders', () => {
    const result = buildTree([hit('a/b/item')]);
    expect(result.folders?.a.path).toBe('a');
    expect(result.folders?.a.folders?.b.path).toBe('a/b');
  });

  it('groups multiple items under the same folder', () => {
    const item1 = hit('folder/item1', 'v1');
    const item2 = hit('folder/item2', 'v2');
    const result = buildTree([item1, item2]);
    const leaves = result.folders?.folder.leaves ?? [];
    expect(leaves).toHaveLength(2);
    expect(leaves).toEqual(expect.arrayContaining([item1, item2]));
  });

  it('handles multiple top-level folders independently', () => {
    const hitA = hit('folderA/item', 'a');
    const hitB = hit('folderB/item', 'b');
    const result = buildTree([hitA, hitB]);
    expect(result.folders?.folderA.leaves).toEqual([hitA]);
    expect(result.folders?.folderB.leaves).toEqual([hitB]);
  });

  it('handles a mix of top-level leaves and folder items', () => {
    const flat = hit('flat-item', 'flat');
    const nested = hit('folder/item', 'nested');
    const result = buildTree([flat, nested]);
    expect(result.leaves).toEqual([flat]);
    expect(result.folders?.folder.leaves).toEqual([nested]);
  });

  it('places items across sibling folders at different depths', () => {
    const shallow = hit('a/item', 'shallow');
    const deep = hit('a/b/item', 'deep');
    const result = buildTree([shallow, deep]);
    expect(result.folders?.a.leaves).toEqual([shallow]);
    expect(result.folders?.a.folders?.b.leaves).toEqual([deep]);
  });

  it('preserves all item fields on leaves', () => {
    const rich: Item = { type: 'reference', value: 'https://example.com', path: 'links/example' };
    const result = buildTree([rich]);
    expect(result.folders?.links.leaves?.[0]).toEqual(rich);
  });
});
