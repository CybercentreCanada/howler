import { get, set, sortBy, take } from 'lodash-es';
import type { Item } from 'models/entities/generated/Item';
import type { Tree } from './types';

export const buildTree = (items: Item[] = []): Tree => {
  // Root tree node stores direct children in `leaves`; subfolders live under `folders`.
  const tree: any = { leaves: [], path: '' };

  sortBy(items, 'path').forEach(item => {
    // Ignore items that cannot be placed in the folder structure.
    if (!item?.path) {
      return;
    }

    // Split path into folder segments + item name, then remove the item name.
    const parts = item.path.split('/');
    parts.pop();

    // Ensure each folder node exists and has its path set.
    parts.forEach((_, index) => {
      const folderPath = `folders.${take(parts, index + 1).join('.folders.')}`;
      set(tree, `${folderPath}.path`, take(parts, index + 1).join('/'));
    });

    if (parts.length > 0) {
      // Navigate to the target folder via the `folders` nesting and append the leaf.
      const folderPath = `folders.${parts.join('.folders.')}`;
      const size = (get(tree, folderPath) as Tree)?.leaves?.length ?? 0;
      set(tree, `${folderPath}.leaves.${size}`, item);
      return;
    }

    // Items without parent folders are top-level leaves.
    tree.leaves.push(item);
  });

  return tree;
};
