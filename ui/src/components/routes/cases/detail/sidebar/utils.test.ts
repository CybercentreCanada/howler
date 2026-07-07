import type { Item } from 'models/entities/generated/Item';
import { describe, expect, it } from 'vitest';
import { buildTree } from './utils';

describe('buildTree', () => {
  it('returns an empty tree for no items', () => {
    const result = buildTree();
    expect(result.leaves).toEqual([]);
    expect(result.folders).toEqual({});
  });

  it('returns an empty tree for an empty array', () => {
    const result = buildTree([]);
    expect(result.leaves).toEqual([]);
    expect(result.folders).toEqual({});
  });

  it('places items at root when parent is null', () => {
    const item: Item = { id: 'item-1', type: 'hit', value: 'hit-001', parent: null };
    const result = buildTree([item]);
    expect(result.leaves).toEqual([item]);
  });

  it('places items at root when parent is undefined', () => {
    const item: Item = { id: 'item-1', type: 'hit', value: 'hit-001' };
    const result = buildTree([item]);
    expect(result.leaves).toEqual([item]);
  });

  it('places items inside a folder by parent reference', () => {
    const folder: Item = { id: 'folder-1', type: 'folder', value: 'My Folder', parent: null };
    const item: Item = { id: 'item-1', type: 'hit', value: 'hit-001', parent: 'folder-1' };
    const result = buildTree([folder, item]);
    expect(result.folders?.['My Folder']).toBeDefined();
    expect(result.folders?.['My Folder'].leaves).toEqual([item]);
  });

  it('renders empty folders', () => {
    const folder: Item = { id: 'folder-1', type: 'folder', value: 'Empty', parent: null };
    const result = buildTree([folder]);
    expect(result.folders?.Empty).toBeDefined();
    expect(result.folders?.Empty.leaves).toEqual([]);
  });

  it('nests folders inside other folders', () => {
    const parent: Item = { id: 'f1', type: 'folder', value: 'Parent', parent: null };
    const child: Item = { id: 'f2', type: 'folder', value: 'Child', parent: 'f1' };
    const item: Item = { id: 'i1', type: 'hit', value: 'hit-1', parent: 'f2' };
    const result = buildTree([parent, child, item]);
    expect(result.folders?.Parent.folders?.Child.leaves).toEqual([item]);
  });

  it('includes folder id in tree nodes', () => {
    const folder: Item = { id: 'folder-1', type: 'folder', value: 'Folder', parent: null };
    const result = buildTree([folder]);
    expect(result.folders?.Folder.id).toBe('folder-1');
  });

  it('includes parentId in tree nodes', () => {
    const parent: Item = { id: 'f1', type: 'folder', value: 'Parent', parent: null };
    const child: Item = { id: 'f2', type: 'folder', value: 'Child', parent: 'f1' };
    const result = buildTree([parent, child]);
    expect(result.folders?.Parent.parentId).toBeNull();
    expect(result.folders?.Parent.folders?.Child.parentId).toBe('f1');
  });

  it('places orphaned items at root when parent folder is missing', () => {
    const item: Item = { id: 'i1', type: 'hit', value: 'hit-1', parent: 'missing-folder' };
    const result = buildTree([item]);
    expect(result.leaves).toEqual([item]);
  });

  it('handles markdown items', () => {
    const markdown: Item = { id: 'md-1', type: 'markdown', value: '# Hello', parent: null };
    const result = buildTree([markdown]);
    expect(result.leaves).toEqual([markdown]);
  });

  it('handles multiple root-level items', () => {
    const a: Item = { id: 'a', type: 'hit', value: 'hit-a' };
    const b: Item = { id: 'b', type: 'event', value: 'event-b' };
    const result = buildTree([a, b]);
    expect(result.leaves).toHaveLength(2);
  });

  it('handles multiple items in the same folder', () => {
    const folder: Item = { id: 'f1', type: 'folder', value: 'Alerts', parent: null };
    const a: Item = { id: 'a', type: 'hit', value: 'hit-a', parent: 'f1' };
    const b: Item = { id: 'b', type: 'hit', value: 'hit-b', parent: 'f1' };
    const result = buildTree([folder, a, b]);
    expect(result.folders?.Alerts.leaves).toHaveLength(2);
  });

  it('handles items with name field', () => {
    const item: Item = { id: 'i1', type: 'hit', value: 'hit-1', name: 'My Hit' };
    const result = buildTree([item]);
    expect(result.leaves?.[0].name).toBe('My Hit');
  });

  it('preserves all item fields on leaves', () => {
    const rich: Item = { id: 'r1', type: 'reference', value: 'https://example.com', name: 'Example', parent: null };
    const result = buildTree([rich]);
    expect(result.leaves?.[0]).toEqual(rich);
  });
});
