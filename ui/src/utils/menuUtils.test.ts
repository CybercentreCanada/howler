/// <reference types="vitest" />
import type { AppLeftNavElement, AppLeftNavGroup, AppLeftNavItem } from 'commons/components/app/AppConfigs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppMenuBuilder from './menuUtils';

// Avoid pulling in react-pluggable (and its transitive React deps) by mocking the store module.
// vi.mock is hoisted by Vitest before any imports, so the mock is applied even though this call appears below the imports.
vi.mock('plugins/store', () => ({
  MainMenuInsertOperation: {
    Insert: 'INSERT',
    InsertAfter: 'AFTER',
    InsertBefore: 'BEFORE'
  }
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeItem = (id: string, overrides: Partial<AppLeftNavItem> = {}): AppLeftNavElement => ({
  type: 'item',
  element: { id, i18nKey: `key.${id}`, route: `/${id}`, ...overrides }
});

const makeGroup = (id: string, items: AppLeftNavItem[] = []): AppLeftNavElement => ({
  type: 'group',
  element: { id, i18nKey: `key.${id}`, items } as AppLeftNavGroup
});

const makeDivider = (): AppLeftNavElement => ({ type: 'divider', element: null });

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AppMenuBuilder', () => {
  let initial: AppLeftNavElement[];
  let builder: AppMenuBuilder;

  beforeEach(() => {
    initial = [makeItem('home'), makeItem('search'), makeGroup('tools', [{ id: 'view', route: '/view' }])];
    builder = new AppMenuBuilder(initial);
  });

  // -------------------------------------------------------------------------
  // menu getter
  // -------------------------------------------------------------------------
  describe('menu getter', () => {
    it('returns the initial menu unchanged when no operations are applied', () => {
      expect(builder.menu).toHaveLength(3);
    });
  });

  // -------------------------------------------------------------------------
  // indexOfMenuId
  // -------------------------------------------------------------------------
  describe('indexOfMenuId', () => {
    it('returns index -1 for the "root" pseudo-target', () => {
      expect(builder.indexOfMenuId('root')).toEqual({ index: -1 });
    });

    it('returns the correct top-level index for a root item', () => {
      expect(builder.indexOfMenuId('home')).toEqual({ index: 0 });
    });

    it('returns both index and subIndex for a nested item', () => {
      expect(builder.indexOfMenuId('view')).toEqual({ index: 2, subIndex: 0 });
    });

    it('throws for an unknown id', () => {
      expect(() => builder.indexOfMenuId('unknown-id')).toThrow();
    });
  });

  // -------------------------------------------------------------------------
  // insert
  // -------------------------------------------------------------------------
  describe('insert', () => {
    it('appends a new item to the root when targetId is "root"', () => {
      builder.insert('root', makeItem('new'));
      expect(builder.menu).toHaveLength(4);
      expect((builder.menu[3] as any).element.id).toBe('new');
    });

    it('appends a new item to an existing group', () => {
      builder.insert('tools', makeItem('extra'));
      const group = builder.menu.find(el => el.type === 'group') as any;
      expect(group.element.items).toHaveLength(2);
      expect(group.element.items[1].id).toBe('extra');
    });

    it('converts a root-level item into a group when inserting into it', () => {
      builder.insert('home', makeItem('sub-home'));
      const converted = builder.menu.find(el => el.type === 'group') as any;
      // The first group found should be the newly converted one.
      expect(converted).toBeDefined();
      expect(converted.element.items.some((i: AppLeftNavItem) => i.id === 'sub-home')).toBe(true);
    });

    it('marks nested items added to a group as nested:true', () => {
      builder.insert('tools', makeItem('nested-item'));
      const group = builder.menu.find(el => el.type === 'group') as any;
      const last = group.element.items[group.element.items.length - 1];
      expect(last.nested).toBe(true);
    });

    it('does not insert a divider into a group (logs warning and returns)', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const before = (builder.menu.find(el => el.type === 'group') as any).element.items.length;
      builder.insert('tools', makeDivider());
      const after = (builder.menu.find(el => el.type === 'group') as any).element.items.length;
      expect(after).toBe(before);
      warnSpy.mockRestore();
    });
  });

  // -------------------------------------------------------------------------
  // insertBefore
  // -------------------------------------------------------------------------
  describe('insertBefore', () => {
    it('inserts a new root-level item before the target', () => {
      builder.insertBefore('search', makeItem('before-search'));
      // 'search' was at index 1; the new item should now be at index 1.
      expect((builder.menu[1] as any).element.id).toBe('before-search');
      expect((builder.menu[2] as any).element.id).toBe('search');
    });

    it('inserts before the first root item (index 0)', () => {
      builder.insertBefore('home', makeItem('new-first'));
      expect((builder.menu[0] as any).element.id).toBe('new-first');
    });

    it('inserts a new nested item before a sub-item within its group', () => {
      builder.insertBefore('view', makeItem('before-view'));
      const group = builder.menu.find(el => el.type === 'group') as any;
      expect(group.element.items[0].id).toBe('before-view');
      expect(group.element.items[1].id).toBe('view');
    });

    it('marks items inserted into a group as nested:true', () => {
      builder.insertBefore('view', makeItem('nested-before'));
      const group = builder.menu.find(el => el.type === 'group') as any;
      expect(group.element.items[0].nested).toBe(true);
    });

    it('does not insert a divider before a sub-item (logs warning)', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const before = (builder.menu.find(el => el.type === 'group') as any).element.items.length;
      builder.insertBefore('view', makeDivider());
      const after = (builder.menu.find(el => el.type === 'group') as any).element.items.length;
      expect(after).toBe(before);
      warnSpy.mockRestore();
    });
  });

  // -------------------------------------------------------------------------
  // insertAfter
  // -------------------------------------------------------------------------
  describe('insertAfter', () => {
    it('inserts a new root-level item after the target', () => {
      builder.insertAfter('home', makeItem('after-home'));
      expect((builder.menu[1] as any).element.id).toBe('after-home');
      expect((builder.menu[2] as any).element.id).toBe('search');
    });

    it('inserts after the last root item', () => {
      builder.insertAfter('tools', makeItem('very-last'));
      expect((builder.menu[builder.menu.length - 1] as any).element.id).toBe('very-last');
    });

    it('inserts a new nested item after a sub-item within its group', () => {
      builder.insertAfter('view', makeItem('after-view'));
      const group = builder.menu.find(el => el.type === 'group') as any;
      expect(group.element.items[0].id).toBe('view');
      expect(group.element.items[1].id).toBe('after-view');
    });

    it('marks items inserted into a group as nested:true', () => {
      builder.insertAfter('view', makeItem('nested-after'));
      const group = builder.menu.find(el => el.type === 'group') as any;
      expect(group.element.items[1].nested).toBe(true);
    });

    it('does not insert a divider after a sub-item (logs warning)', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const before = (builder.menu.find(el => el.type === 'group') as any).element.items.length;
      builder.insertAfter('view', makeDivider());
      const after = (builder.menu.find(el => el.type === 'group') as any).element.items.length;
      expect(after).toBe(before);
      warnSpy.mockRestore();
    });
  });

  // -------------------------------------------------------------------------
  // applyOperations
  // -------------------------------------------------------------------------
  describe('applyOperations', () => {
    it('applies an INSERT operation to the root', () => {
      builder.applyOperations([{ operation: 'INSERT', targetId: 'root', item: makeItem('op-item') }]);
      expect(builder.menu.some((el: any) => el.element?.id === 'op-item')).toBe(true);
    });

    it('applies a BEFORE operation', () => {
      builder.applyOperations([{ operation: 'BEFORE', targetId: 'search', item: makeItem('before-op') }]);
      const idx = builder.menu.findIndex((el: any) => el.element?.id === 'before-op');
      const searchIdx = builder.menu.findIndex((el: any) => el.element?.id === 'search');
      expect(idx).toBeLessThan(searchIdx);
    });

    it('applies an AFTER operation', () => {
      builder.applyOperations([{ operation: 'AFTER', targetId: 'home', item: makeItem('after-op') }]);
      const homeIdx = builder.menu.findIndex((el: any) => el.element?.id === 'home');
      const afterIdx = builder.menu.findIndex((el: any) => el.element?.id === 'after-op');
      expect(afterIdx).toBe(homeIdx + 1);
    });

    it('applies multiple operations in order', () => {
      builder.applyOperations([
        { operation: 'INSERT', targetId: 'root', item: makeItem('first') },
        { operation: 'INSERT', targetId: 'root', item: makeItem('second') }
      ]);
      const ids = builder.menu.map((el: any) => el.element?.id).filter(Boolean);
      expect(ids).toContain('first');
      expect(ids).toContain('second');
    });

    it('ignores operations with unknown operation strings', () => {
      const lenBefore = builder.menu.length;
      builder.applyOperations([{ operation: 'UNKNOWN', targetId: 'root', item: makeItem('x') }]);
      expect(builder.menu.length).toBe(lenBefore);
    });
  });
});
