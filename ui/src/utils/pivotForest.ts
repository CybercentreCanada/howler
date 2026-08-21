import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';

export type menuPathNode = {
  path: string;
  pivots?: Pivot[];
  children?: menuPathNode[];
};

export type PivotTree = {
  pivot?: Pivot[];
  [key: string]: PivotTree | Pivot[];
};

/**
 *
 * This helper is use to organize pivot into a forest. Since we do not know before the groupPivot run if some dossier
 * had common pivot, we need to make the forest more complex, the PathMap later on this file simplify the forest to the
 * least amount of path possible for each pivot so if only one item is under the totality of Clue/information/ipLocation
 * The path here will be [Clue][information][ipLocation] after buildPathMap it would be [Clue/information/ipLocations]
 * This is use to group them in HitLinks.tsx
 *@param dossiers array of dossier we want to organize the pivots of
 *
 * @returns {
 *   "root"{
 *     "other parent" {
 *     "other parent"{...}
 *       "pivot":[]
 *     },
 *     "pivot":[]
 *   }
 * }
 *
 *
 */
const getGroupPivot = (dossiers: Dossier[]) => {
  const groupPivot: PivotTree = {};

  for (const dossier of dossiers) {
    if (!dossier.pivots) {
      continue; // fall safe
    }

    for (const pivot of dossier.pivots) {
      let current: PivotTree = groupPivot;

      // if we have a group we move the pointer to the proper location
      if (pivot.group && pivot.group !== '') {
        const group = pivot.group.split('/');
        for (let i = 0; i < group.length; i++) {
          if (!(group[i] in current)) {
            current[group[i]] = {};
          }
          current = current[group[i]] as PivotTree;
        }
      }

      // Add the pivot section, this(pivot) is reserved inside of the DossierGroupValidation check and the back end.
      if (!('pivot' in current)) {
        current['pivot'] = [];
      }

      // Add the pivot to its location
      current['pivot'].push(pivot);
    }
  }
  return groupPivot;
};

const buildPathMap = (tree: PivotTree): menuPathNode[] => {
  const nodes: menuPathNode[] = [];

  for (const key in tree) {
    if (key == 'pivot') {
      continue;
    } // this is not a branch these are buttons we solve it earlier

    let path: string = key;
    let current = tree[key] as PivotTree;
    // Check how long we can go without having more then one tree branch
    // if pivot is present, this mean buttons are there, if its length 1 it mean there is only 1 path towards the next buttons
    while (Object.keys(current).length === 1 && !('pivot' in current)) {
      const newKey: string = Object.keys(current)[0];
      path = path + `/${newKey}`;
      current = current[newKey] as PivotTree; // Will always be a PivotTree if its not pivot
    }

    // Build the array
    nodes.push({ path: path, pivots: current['pivot'] ?? [], children: buildPathMap(current) });
  }

  return nodes;
};

const pivotForest = (dossiers: Dossier[]) => {
  const group = getGroupPivot(dossiers);
  const nodes: menuPathNode[] = [];
  if ('pivot' in group) {
    nodes.push({ path: '', pivots: group['pivot'] as Pivot[], children: [] });
  }
  nodes.push(...buildPathMap(group));
  return nodes;
};

export default pivotForest;
