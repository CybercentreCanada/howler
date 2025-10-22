import { MainMenuInsertOperation } from '../plugins/store';
import type { AppLeftNavElement } from '../commons/components/app/AppConfigs';

class AppMenuBuilder {
  private items: AppLeftNavElement[];
  private indexMap: {};

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
    const targetMenu = this.menuFromIndex(menuLocation.index, menuLocation.subIndex);

    if (targetMenu.type === 'group') {
      if (item.type == 'divider') {
        console.log(
          `Skipping DIVIDER Operation: INSERT on Target: ${targetId}, Dividers cannot be inserted to sub-menus`
        );
        return;
      }
      // This is a group, add to end of group
      item.element['nested'] = true;
      targetMenu.element.items.push(item);
    } else {
      // Check if this is a root 'item'
      if (menuLocation.index !== -1 && menuLocation.subIndex == null) {
        if (item.type == 'divider') {
          console.log(
            `Skipping DIVIDER Operation: INSERT on Target: ${targetId}, Dividers cannot be inserted to sub-menus`
          );
          return;
        }
        // We are trying insert item into a non-group menu item,
        // make it a group
        targetMenu.type = 'group';
        targetMenu.element.items = [item.element];
        delete targetMenu.element.route;
      } else {
        // Standard root menu item, push to array
        targetMenu.push(item.element);
      }
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
      if (item.type == 'divider') {
        console.log(
          `Skipping DIVIDER Operation: INSERTBEFORE on Target: ${targetId}, Dividers cannot be inserted to sub-menus`
        );
        return;
      }

      const targetMenu = this.menuFromIndex(menuLocation.index);
      item.element['nested'] = true;
      targetMenu.element['items'].splice(menuLocation.subIndex, 0, item.element);
    } else {
      if (menuLocation.index < 0) {
        menuLocation.index = 0;
      }
      this.items.splice(menuLocation.index, 0, item);
    }
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
      if (item.type == 'divider') {
        console.log(
          `Skipping DIVIDER Operation: INSERTAFTER on Target: ${targetId}, Dividers cannot be inserted to sub-menus`
        );
        return;
      }

      const targetMenu = this.menuFromIndex(menuLocation.index);
      item.element['nested'] = true;
      targetMenu.element['items'].splice(menuLocation.subIndex + 1, 0, item.element);
    } else {
      if (menuLocation.index < 0) {
        menuLocation.index = this.items.length;
      }

      this.items.splice(menuLocation.index + 1, 0, item);
    }
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
        return { index: this.indexMap[id]['parent'], subIndex: this.indexMap[id]['index'] };
      }
      return { index: this.indexMap[id]['index'] };
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
  menuFromIndex(index: number, subIndex?: number) {
    if (index === -1) {
      return this.items;
    } else {
      if (!subIndex) {
        return this.items[index];
      } else {
        return this.items[index]['element']['items'][subIndex];
      }
    }
  }

  /**
   * Creates a flat list of menu items and subitems by menu id
   * for quick lookup.
   *
   * @private
   */
  private updateMenuMap() {
    let indexMap = {};

    for (let index = 0; index < this.items.length; index++) {
      let menuItem = this.items[index];
      if (menuItem['type'] != 'divider') {
        indexMap[menuItem['element']['id']] = { index: index };

        if (menuItem['type'] == 'group') {
          //indexMap[menuItem['element']['id']]['items'] = {}
          for (let subIndex = 0; subIndex < menuItem['element']['items'].length; subIndex++) {
            let subMenuItem = menuItem['element']['items'][subIndex];
            indexMap[subMenuItem['id']] = { index: subIndex, parent: index };
          }
        }
      }
    }

    this.indexMap = indexMap;
  }
}

export default AppMenuBuilder;
