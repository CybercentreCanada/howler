import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';

export type PivotTree = {
  pivot?: Pivot[];
  [key: string]: PivotTree | Pivot[];
};

/**
 *
 * This helper is use to organize pivot into a forest.
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

// find parent pivot per tree
const findFirstPivotInTree = (tree: PivotTree) => {
  if ('pivot' in tree && tree.pivot.length > 0) {
    return [tree.pivot[0]];
  }
  const collectedPivot: Pivot[] = [];

  for (const branch of Object.keys(tree)) {
    if (branch === 'pivot') continue;

    // Add other path coming from this branch with no direct parents
    collectedPivot.push(...findFirstPivotInTree(tree[branch] as PivotTree));
  }
  return collectedPivot;
};

const pivotGrouping = (dossiers: Dossier[]): Pivot[] => {
  const groupPivot = getGroupPivot(dossiers);
  const shownPivot: Pivot[] = [];

  // pivot with no group
  if ('pivot' in groupPivot && groupPivot.pivot.length > 0) {
    shownPivot.push(...groupPivot.pivot);
  }

  // find other branch pivot
  for (const root in groupPivot) {
    if (root === 'pivot') continue; // treated before
    shownPivot.push(...findFirstPivotInTree(groupPivot[root] as PivotTree));
  }

  return shownPivot;
};

export default pivotGrouping;
