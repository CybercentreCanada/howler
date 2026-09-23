/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest';
import { codeTabs } from './tabs';

describe('markdown codeTabs plugin', () => {
  it('converts consecutive tabbed code blocks into a tabs payload', () => {
    const tree: any = {
      type: 'root',
      children: [
        { type: 'code', lang: 'ts', meta: 'tab="Alpha"', value: 'a()' },
        { type: 'code', lang: 'py', meta: 'tab="Beta"', value: 'b()' }
      ]
    };
    const file = { message: vi.fn() };

    codeTabs()(tree, file as any);

    expect(tree.children).toHaveLength(1);
    expect(tree.children[0]).toMatchObject({ lang: 'tabs' });
    expect(JSON.parse(tree.children[0].value)).toEqual([
      { title: 'Alpha', lang: 'ts', value: 'a()' },
      { title: 'Beta', lang: 'py', value: 'b()' }
    ]);
  });

  it('inserts a title node for a single tabbed block and reports invalid metadata', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const tree: any = {
      type: 'root',
      children: [{ type: 'code', lang: 'ts', meta: 'tab="Alpha"', value: 'a()' }]
    };
    const file = { message: vi.fn() };

    codeTabs()(tree, file as any);

    expect(tree.children[0]).toMatchObject({
      type: 'paragraph',
      data: { hProperties: { 'data-remark-code-title': true, 'data-language': 'ts' } }
    });

    const invalidTree: any = {
      type: 'root',
      children: [{ type: 'code', lang: 'ts', meta: 'tab=', value: 'oops' }]
    };
    codeTabs()(invalidTree, file as any);
    expect(file.message).toHaveBeenCalledWith('Invalid tab title', invalidTree.children[0], 'remark-code-title');

    const brokenChain: any = {
      type: 'root',
      children: [
        { type: 'code', lang: 'ts', meta: 'tab="Alpha"', value: 'a()' },
        { type: 'code', lang: 'py', meta: 'tab=', value: 'b()' }
      ]
    };
    codeTabs()(brokenChain, file as any);
    expect(warnSpy).toHaveBeenCalledWith('Failed to parse tab title.');
  });
});
