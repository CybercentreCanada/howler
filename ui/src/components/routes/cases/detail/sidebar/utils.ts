import { get, set } from 'lodash-es';
import type { Item } from 'models/entities/generated/Item';
import type { Tree } from './types';

export const buildTree = (items: Item[] = []): Tree => {
  // Root tree node stores direct children in `leaves` and nested folders as object keys.
  const tree: Tree = { leaves: [] };

  items.forEach(item => {
    // Ignore items that cannot be placed in the folder structure.
    if (!item?.path) {
      return;
    }

    // Split path into folder segments + item name, then remove the item name.
    const parts = item.path.split('/');
    parts.pop();

    if (parts.length > 0) {
      // Use dot notation so lodash `get/set` can address nested folder objects.
      const key = parts.join('.');
      const size = (get(tree, key) as Tree)?.leaves?.length || 0;

      // Append this item to the folder's `leaves` array.
      set(tree, `${key}.leaves.${size}`, item);
      return;
    }

    // Items without parent folders are top-level leaves.
    tree.leaves.push(item);
  });

  return tree;
};
