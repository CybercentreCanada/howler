import { sortBy } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';

export type menuPathNode = {
  path: string;
  pivots?: dossierPivot[];
  children?: menuPathNode[];
};

type dossierPivot = {
  pivot: Pivot;
  dossier: Dossier;
};

type PivotTree = {
  pivot?: dossierPivot[];
  [key: string]: PivotTree | dossierPivot[];
};

/**
 *
 * This helper is use to organize pivot into a forest, one folder per group path segment.
 * A pivot with group "network/dns" produces a "network" node whose only child is "dns",
 * so the menu structure mirrors the group path exactly, with no segments skipped or merged.
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

    const current = tree[key] as PivotTree;

    // Build the array; each group path segment is always its own node, never merged with its parent or child
    nodes.push({
      path: key,
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
