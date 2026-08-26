import { sortBy } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';

export type menuPathNode = {
  path: string;
  pivots?: dossierPivot[];
  children?: menuPathNode[];
};

export type dossierPivot = {
  pivot: Pivot;
  dossier: Dossier;
};

type PivotTree = {
  pivot?: dossierPivot[];
  [key: string]: PivotTree | dossierPivot[];
};

/**
 *
 * This helper is use to organize pivot into a forest. A chain of path segments that has no branching and no
 * pivots of its own (e.g. "network/ip/v4" with nothing else under "ip" or "v4") is squashed into a single node
 * labeled with the full chain, so the menu doesn't force a hover through several empty, single-choice folders.
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
      current['pivot'].push({ pivot: pivot, dossier: dossier });
    }
  }
  return groupPivot;
};

const buildPathMap = (tree: PivotTree, language = 'en'): menuPathNode[] => {
  const nodes: menuPathNode[] = [];
  for (const key in tree) {
    if (key == 'pivot') {
      continue;
    } // this is not a branch these are buttons we solve it earlier

    let path: string = key;
    let current = tree[key] as PivotTree;
    // squash a chain as long as it neither branches nor carries pivots of its own; that's a pure "pass-through"
    // segment, so its name is folded into the path instead of forcing its own empty menu level
    while (Object.keys(current).length === 1 && !('pivot' in current)) {
      const newKey: string = Object.keys(current)[0];
      path = path + `/${newKey}`;
      current = current[newKey] as PivotTree;
    }

    nodes.push({
      path: path,
      pivots: sortBy(current['pivot'] ?? [], item => item.pivot.label?.[language]),
      children: buildPathMap(current, language)
    });
  }

  return nodes;
};

const pivotForest = (dossiers: Dossier[], language = 'en'): menuPathNode[] => {
  const group = getGroupPivot(dossiers);
  const nodes: menuPathNode[] = [];

  if ('pivot' in group) {
    nodes.push({ path: '', pivots: group['pivot'] as dossierPivot[], children: [] });
  }

  nodes.push(...buildPathMap(group, language));

  return nodes;
};

export default pivotForest;
