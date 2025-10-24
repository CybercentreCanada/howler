import type { AppLeftNavElement, AppLeftNavGroup, AppLeftNavItem } from '../commons/components/app/AppConfigs';
import { MainMenuInsertOperation } from '../plugins/store';

class AppMenuBuilder {
  private items: AppLeftNavElement[];
  private indexMap: Record<string | number, { index: number; parent?: number }>;

  constructor(defaultMenu: AppLeftNavElement[]) {
    this.items = defaultMenu;
    this.updateMenuMap();
  }


  /**
   * Applies a collection of Menu Operation objects created by the plugin system
   *
   * @param operations Operations created by the plugin system
   */
  applyOperations(operations: { operation: string; targetId: string; item: AppLeftNavElement }[]) {
    for (const operation of operations) {
      switch (operation.operation) {
        case MainMenuInsertOperation.Insert:
          // Inserts at end or adds to sub-elements
          this.insert(operation.targetId, operation.item);
          break;
        case MainMenuInsertOperation.InsertBefore:
          // Inserts before target element
          this.insertBefore(operation.targetId, operation.item);
          break;
        case MainMenuInsertOperation.InsertAfter:
          // Inserts after target element
          this.insertAfter(operation.targetId, operation.item);
          break;
      }
      this.updateMenuMap();
    }
  }

  /**
   * Get the completed menu structure
   */
  get menu() {
    return this.items;
  }

  /**
   * Insert provided menu item at the menu object identified by targetId.
   *
   * If the target menu is a group then item will be placed at end of sub items
   *
   * If the target menu is a standard item then group will be created and new item added, warning this removes
   * the route from the new group parent item, be sure to add it back.
   *
   * If the target is 'root' then item will be added to end of root menu
   *
   * @param targetId Identifier of menu to insert to
   * @param item Menu Item to insert
   */
  insert(targetId: string, item: AppLeftNavElement) {
    const menuLocation = this.indexOfMenuId(targetId);
    const target = this.menuFromIndex(menuLocation.index, menuLocation.subIndex);

    if (!Array.isArray(target) && this.isGroupElement(target)) {
      if (item.type === 'divider') {
        return;
      }
      const group = target.element;
      const newItem: AppLeftNavItem = { ...(item.element as AppLeftNavItem), nested: true };
      group.items = [...group.items, newItem];
      return;
    }

    if (Array.isArray(target)) {
      target.push(item);
      return;
    }

    if (menuLocation.index !== -1 && menuLocation.subIndex == null) {
      if (item.type === 'divider') {
        return;
      }

      if (!this.isItemElement(target)) {
        return;
      }

      const header = target.element;
      const inserted: AppLeftNavItem = { ...(item.element as AppLeftNavItem), nested: true };


      const newGroup: AppLeftNavElement = {
        type: 'group',
        element: {
          id: header.id,
          open: true,
          i18nKey: header.i18nKey,
          title: header.text,
          userPropValidators: header.userPropValidators,
          icon: header.icon as React.ReactElement<any>,
          items: [inserted]
        } as AppLeftNavGroup
      };

      this.items[menuLocation.index] = newGroup;
      return;
    }
  }

  /**
   * Insert provided menu item before the menu object identified by targetId.
   *
   * @param targetId Identifier of menu to insert to
   * @param item Menu Item to insert
   */
  insertBefore(targetId: string, item: AppLeftNavElement) {
    const menuLocation = this.indexOfMenuId(targetId);

    if (menuLocation.subIndex != null) {
      if (item.type === 'divider') {
        return;
      }
      const parentElement = this.menuFromIndex(menuLocation.index);
      if (!Array.isArray(parentElement) && this.isGroupElement(parentElement)) {
        const group = parentElement.element;
        const newItem: AppLeftNavItem = { ...(item.element as AppLeftNavItem), nested: true };
        group.items = [
          ...group.items.slice(0, menuLocation.subIndex),
          newItem,
          ...group.items.slice(menuLocation.subIndex)
        ];
      }
      return;
    }

    // Root level insertion before target index
    if (menuLocation.index < 0) {
      menuLocation.index = 0;
    }
    this.items = [
      ...this.items.slice(0, menuLocation.index),
      item,
      ...this.items.slice(menuLocation.index)
    ];
  }

  /**
   * Insert provided menu item after the menu object identified by targetId.
   *
   * @param targetId Identifier of menu to insert to
   * @param item Menu Item to insert
   */
  insertAfter(targetId: string, item: AppLeftNavElement) {
    const menuLocation = this.indexOfMenuId(targetId);

    if (menuLocation.subIndex != null) {
      if (item.type === 'divider') {
        return;
      }
      const parentElement = this.menuFromIndex(menuLocation.index);
      if (!Array.isArray(parentElement) && this.isGroupElement(parentElement)) {
        const group = parentElement.element;
        const newItem: AppLeftNavItem = { ...(item.element as AppLeftNavItem), nested: true };
        group.items = [
          ...group.items.slice(0, menuLocation.subIndex + 1),
          newItem,
          ...group.items.slice(menuLocation.subIndex + 1)
        ];
      }
      return;
    }

    // Root level insertion after target index
    if (menuLocation.index < 0) {
      menuLocation.index = this.items.length;
    }
    this.items = [
      ...this.items.slice(0, menuLocation.index + 1),
      item,
      ...this.items.slice(menuLocation.index + 1)
    ];
  }

  /**
   * Locates menu location in menu structure by menu id.
   *
   * @param id Menu Id to search for
   * @return {index: number, subIndex: number} A dictionary containing indexes needed to access Menu Item
   */
  indexOfMenuId(id: string): { index: number; subIndex?: number } {
    if (id === 'root') {
      // Root item so return entire menu
      return { index: -1 };
    } else if (id in this.indexMap) {
      // Item exists, check if it's a subitem
      if ('parent' in this.indexMap[id]) {
        return { index: this.indexMap[id].parent, subIndex: this.indexMap[id].index };
      }
      return { index: this.indexMap[id].index };
    } else {
      throw new Error(`Menu element with id of '${id}' not found.`);
    }
  }

  /**
   *  Grabs a menu by indexes, helper function to account for an index of -1
   *  to represent the root menu
   *
   * @param index First level index
   * @param subIndex Second level index
   * @return {} Menu item
   */
  menuFromIndex(index: number, subIndex?: number): AppLeftNavElement[] | AppLeftNavElement | AppLeftNavItem {
    if (index === -1) {
      return this.items;
    }
    if (subIndex == null) {
      return this.items[index];
    }
    const menuItem = this.items[index];
    if (menuItem.type === 'group') {
      return menuItem.element.items[subIndex];
    }
    throw new Error(`Menu item at index ${index} is not a group and does not have sub-items.`);
  }

  private isGroupElement(elem: unknown): elem is { type: 'group'; element: AppLeftNavGroup } {
    return !!elem && typeof elem === 'object' && (elem as AppLeftNavElement).type === 'group';
  }

  private isItemElement(elem: unknown): elem is { type: 'item'; element: AppLeftNavItem } {
    return !!elem && typeof elem === 'object' && (elem as AppLeftNavElement).type === 'item';
  }

  /**
   * Creates a flat list of menu items and subitems by menu id
   * for quick lookup.
   *
   * @private
   */
  private updateMenuMap() {
    const indexMap: Record<string | number, { index: number; parent?: number }> = {};
    for (let index = 0; index < this.items.length; index++) {
      const menuItem = this.items[index];
      if (menuItem.type === 'divider') {
        continue;
      }
      indexMap[menuItem.element.id] = { index };
      if (menuItem.type === 'group') {
        for (let subIndex = 0; subIndex < menuItem.element.items.length; subIndex++) {
          const subMenuItem = menuItem.element.items[subIndex];
          indexMap[subMenuItem.id] = { index: subIndex, parent: index };
        }
      }
    }
    this.indexMap = indexMap;
  }
}

export default AppMenuBuilder;
