import type { LeftNavMenuItem, LeftNavMenuProps, LeftNavRouteProps } from '@tui/core';
import type { MainMenuOperation } from 'plugins/store';
import { describe, expect, it } from 'vitest';
import { applyMainMenuOperations } from './menuUtils';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeItem = (id: string, overrides: Partial<LeftNavRouteProps> = {}): LeftNavRouteProps => ({
  id,
  type: 'route',
  i18nKey: `key.${id}`,
  route: `/${id}`,
  ...overrides
});

const makeGroup = (id: string, items: LeftNavMenuItem[] = []): LeftNavMenuProps => ({
  id,
  type: 'menu',
  i18nKey: `key.${id}`,
  items
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('applyMainMenuOperations', () => {
  const root = (): LeftNavMenuProps =>
    makeGroup('root', [makeItem('home'), makeItem('search'), makeGroup('tools', [makeItem('view')])]);

  it('appends an item to the explicit root menu without mutating it', () => {
    const initial = root();
    const result = applyMainMenuOperations(initial, [{ type: 'append', parentId: 'root', item: makeItem('new') }]);

    expect(result.items.map(item => item.id)).toEqual(['home', 'search', 'tools', 'new']);
    expect(initial.items.map(item => item.id)).toEqual(['home', 'search', 'tools']);
  });

  it('appends an item to a nested menu', () => {
    const result = applyMainMenuOperations(root(), [{ type: 'append', parentId: 'tools', item: makeItem('extra') }]);
    const tools = result.items.find(item => item.id === 'tools') as LeftNavMenuProps;

    expect(tools.items.map(item => item.id)).toEqual(['view', 'extra']);
  });

  it('inserts relative to an item at any depth', () => {
    const result = applyMainMenuOperations(root(), [
      { type: 'insertRelative', anchorId: 'view', position: 'before', item: makeItem('before-view') },
      { type: 'insertRelative', anchorId: 'search', position: 'after', item: makeItem('after-search') }
    ]);
    const tools = result.items.find(item => item.id === 'tools') as LeftNavMenuProps;

    expect(result.items.map(item => item.id)).toEqual(['home', 'search', 'after-search', 'tools']);
    expect(tools.items.map(item => item.id)).toEqual(['before-view', 'view']);
  });

  it('removes items at any depth', () => {
    const result = applyMainMenuOperations(root(), [
      { type: 'remove', targetId: 'search' },
      { type: 'remove', targetId: 'view' }
    ]);
    const tools = result.items.find(item => item.id === 'tools') as LeftNavMenuProps;

    expect(result.items.map(item => item.id)).toEqual(['home', 'tools']);
    expect(tools.items).toHaveLength(0);
  });

  it('rejects appending to a route instead of converting it into a menu', () => {
    expect(() =>
      applyMainMenuOperations(root(), [{ type: 'append', parentId: 'home', item: makeItem('child') }])
    ).toThrow("Menu 'home' does not exist or is not a menu.");
  });

  it('rejects duplicate item ids', () => {
    const operations: MainMenuOperation[] = [
      { type: 'insertRelative', anchorId: 'home', position: 'after', item: makeItem('home') }
    ];

    expect(() => applyMainMenuOperations(root(), operations)).toThrow("Menu item with id 'home' already exists.");
  });
});
