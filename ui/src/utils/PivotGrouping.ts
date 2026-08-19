import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';

type PivotTree = {
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
const pivotGrouping = (dossiers: Dossier[]): PivotTree => {
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

export default pivotGrouping;
