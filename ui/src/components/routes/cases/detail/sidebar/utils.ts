import { sortBy } from 'lodash-es';
import type { Item } from 'models/entities/generated/Item';
import type { Tree } from './types';

/**
 * Build a tree from a flat array of items using parent-based relationships.
 *
 * Folder items (type=folder) become tree nodes whose children are items
 * referencing the folder's `id` as their `parent`.
 * Items with `parent=null` or `parent=undefined` are root-level.
 */
export const buildTree = (items: Item[] = []): Tree => {
  const root: Tree = { item: null as unknown as Item, leaves: [], folders: {} };

  // Index folders by id
  const folderNodes: Record<string, Tree> = {};
  const folderItems = items.filter(item => item.type === 'folder');

  for (const folder of folderItems) {
    if (folder.id) {
      folderNodes[folder.id] = {
        leaves: [],
        folders: {},
        item: folder
      };
    }
  }

  // Build folder hierarchy
  for (const folder of folderItems) {
    if (!folder.id) {
      continue;
    }
    const node = folderNodes[folder.id];
    const folderName = folder.name ?? folder.value ?? folder.id;
    if (!folderName) {
      continue;
    }

    if (folder.parent && folderNodes[folder.parent]) {
      folderNodes[folder.parent].folders![folderName] = node;
    } else {
      root.folders![folderName] = node;
    }
  }

  // Place non-folder items
  const nonFolderItems = items.filter(item => item.type !== 'folder');
  for (const item of sortBy(nonFolderItems, 'value')) {
    if (item.parent && folderNodes[item.parent]) {
      folderNodes[item.parent].leaves!.push(item);
    } else {
      root.leaves!.push(item);
    }
  }

  return root;
};
