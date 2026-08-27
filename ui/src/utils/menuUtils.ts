import type { LeftNavMenuItem, LeftNavMenuProps } from '@tui/core';
import type { MainMenuOperation } from 'plugins/store';

const hasId = (menu: LeftNavMenuProps, id: string): boolean => {
  if (menu.id === id) {
    return true;
  }

  return menu.items.some(item => item.id === id || (item.type === 'menu' && hasId(item, id)));
};

const updateMenu = (
  menu: LeftNavMenuProps,
  menuId: string,
  updater: (current: LeftNavMenuProps) => LeftNavMenuProps
): LeftNavMenuProps | null => {
  if (menu.id === menuId) {
    return updater(menu);
  }

  let updated = false;
  const items = menu.items.map(item => {
    if (item.type !== 'menu') {
      return item;
    }

    const next = updateMenu(item, menuId, updater);
    if (!next) {
      return item;
    }

    updated = true;
    return next;
  });

  return updated ? { ...menu, items } : null;
};

const insertRelative = (
  menu: LeftNavMenuProps,
  anchorId: string,
  item: LeftNavMenuItem,
  position: 'before' | 'after'
): LeftNavMenuProps | null => {
  const index = menu.items.findIndex(current => current.id === anchorId);
  if (index >= 0) {
    const insertionIndex = position === 'before' ? index : index + 1;
    return {
      ...menu,
      items: [...menu.items.slice(0, insertionIndex), item, ...menu.items.slice(insertionIndex)]
    };
  }

  let updated = false;
  const items = menu.items.map(current => {
    if (current.type !== 'menu') {
      return current;
    }

    const next = insertRelative(current, anchorId, item, position);
    if (!next) {
      return current;
    }

    updated = true;
    return next;
  });

  return updated ? { ...menu, items } : null;
};

const removeItem = (menu: LeftNavMenuProps, targetId: string): LeftNavMenuProps => ({
  ...menu,
  items: menu.items
    .filter(item => item.id !== targetId)
    .map(item => (item.type === 'menu' ? removeItem(item, targetId) : item))
});

export const applyMainMenuOperations = (
  root: LeftNavMenuProps,
  operations: readonly MainMenuOperation[]
): LeftNavMenuProps => {
  return operations.reduce((menu, operation) => {
    if (operation.type === 'remove') {
      return removeItem(menu, operation.targetId);
    }

    if (hasId(menu, operation.item.id as string)) {
      throw new Error(`Menu item with id '${operation.item.id}' already exists.`);
    }

    if (operation.type === 'append') {
      const next = updateMenu(menu, operation.parentId, current => ({
        ...current,
        items: [...current.items, operation.item]
      }));

      if (next) {
        return next;
      }

      throw new Error(`Menu '${operation.parentId}' does not exist or is not a menu.`);
    }

    const next = insertRelative(menu, operation.anchorId, operation.item, operation.position);
    if (next) {
      return next;
    }

    throw new Error(`Menu item '${operation.anchorId}' does not exist.`);
  }, root);
};
