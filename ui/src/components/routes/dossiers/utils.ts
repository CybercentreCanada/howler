import { sortBy } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';

export interface MenuPathNode {
  path: string;
  pivots?: DossierPivot[];
  children?: MenuPathNode[];
}

// Pair each pivot with its dossier so renderers retain the associated metadata.
export interface DossierPivot {
  pivot: Pivot;
  dossier: Dossier;
}

// Keep node-local pivots separate from user-defined group keys and Object.keys traversal.
const PIVOTS = Symbol('pivots');

interface PivotTree {
  [PIVOTS]?: DossierPivot[];
  [key: string]: PivotTree | DossierPivot[] | undefined;
}

/**
 * Validates a pivot group path using the same rules as the backend service.
 *
 * Rules:
 * - Allows alphabetic characters (including supported accented letters), digits, and '/'.
 * - Rejects malformed paths: consecutive '/', leading '/', or trailing '/'.
 *
 * @param group Requested pivot group path.
 * @returns null when valid, otherwise the i18n error key describing the failure.
 */
export const pivotGroupValidation = (group: string): string | undefined => {
  if (!group || group === '') return;

  // Only contain, French, English, numeral character as well as /.
  if (!/^[0-9A-Za-zùûüÿàâæçéèêëïîôœÙÛÜŸÀÂÆÇÉÈÊËÏÎÔŒ/]*$/.test(group)) {
    return 'route.dossiers.pivots.invalid.character';
  }

  // Protection against wrongly formated /. We need words inbetween and they should not start or end with a /.
  if (group.includes('//') || group.startsWith('/') || group.endsWith('/')) {
    return 'route.dossiers.pivots.invalid.format';
  }
};

const detachedPivotKeys = new WeakMap<Pivot, number>();
let nextDetachedPivotKey = 0;

/**
 * Returns a stable menu key for a pivot within its dossier.
 *
 * Pivots currently attached to the dossier use their array index. Detached
 * pivots receive an object-identity-based fallback key for the module lifetime.
 *
 * @param dossier Dossier containing the pivot, when it is attached.
 * @param pivot Pivot for which to generate a key.
 * @returns A dossier-scoped key suitable for identifying the pivot in the UI.
 */
export const getDossierPivotKey = (dossier: Dossier, pivot: Pivot): string => {
  const pivotIndex = dossier.pivots?.indexOf(pivot) ?? -1;
  if (pivotIndex >= 0) {
    return `${dossier.dossier_id}:${pivotIndex}`;
  }

  let detachedPivotKey = detachedPivotKeys.get(pivot);
  if (detachedPivotKey === undefined) {
    detachedPivotKey = nextDetachedPivotKey++;
    detachedPivotKeys.set(pivot, detachedPivotKey);
  }

  return `${dossier.dossier_id}:${detachedPivotKey}`;
};

/**
 * Builds an intermediate tree keyed by each pivot group segment.
 *
 * Each slash-delimited segment in `pivot.group` creates or reuses a nested
 * node, and pivots at that location are stored in an internal symbol-keyed array.
 * This raw tree is later converted into `menuPathNode[]` for menu rendering.
 *
 * @param dossiers Dossiers whose pivots should be grouped.
 * @returns A nested grouping tree where branch keys are path segments and
 *          each node may contain a symbol-keyed pivot array.
 */
const getGroupPivot = (dossiers: Dossier[]) => {
  // no prototype: group segments are user-defined words (e.g. "constructor", "toString") and must not resolve to inherited Object.prototype keys
  const groupPivot: PivotTree = Object.create(null);

  dossiers.forEach(dossier => {
    dossier.pivots?.forEach(pivot => {
      let current: PivotTree = groupPivot;

      // if we have a group we move the pointer to the proper location
      if (pivot.group) {
        pivot.group.split('/').forEach(groupSegment => {
          if (!(groupSegment in current)) {
            current[groupSegment] = Object.create(null);
          }
          current = current[groupSegment] as PivotTree;
        });
      }

      // Add the pivot to its location.
      current[PIVOTS] ??= [];
      current[PIVOTS].push({ pivot, dossier });
    });
  });

  return groupPivot;
};

/**
 * Converts the intermediate grouping tree into UI menu nodes.
 *
 * While traversing, non-branching chains with no local pivots are squashed
 * into a single `path` label to avoid empty submenu levels in the UI.
 *
 * @param tree Intermediate tree from `getGroupPivot`.
 * @param language Language used to sort pivot labels.
 * @returns A menu node list ready for nested folder rendering.
 */
const buildPathMap = (tree: PivotTree, language: 'en' | 'fr' = 'en'): MenuPathNode[] => {
  const nodes: MenuPathNode[] = [];
  for (const key of Object.keys(tree).sort()) {
    let path: string = key;
    let current = tree[key] as PivotTree;
    // squash a chain as long as it neither branches nor carries pivots of its own; that's a pure "pass-through"
    // segment, so its name is folded into the path instead of forcing its own empty menu level
    while (Object.keys(current).length === 1 && !current[PIVOTS]) {
      const newKey = Object.keys(current)[0];
      path = path + `/${newKey}`;
      current = current[newKey] as PivotTree;
    }

    nodes.push({
      path: path,
      pivots: sortBy(current[PIVOTS] ?? [], item => item.pivot.label?.[language]),
      children: buildPathMap(current, language)
    });
  }

  return nodes;
};

/**
 * Produces the final forest consumed by grouped pivot menus.
 *
 * Root-level pivots (no group path) are emitted as a node with an empty path,
 * then grouped branches are appended from `buildPathMap`.
 *
 * @param dossiers Dossiers to convert into grouped pivot menu nodes.
 * @param language Language used to sort labels inside each node.
 * @returns Forest of menu nodes for hit-related pivot navigation.
 */
export const pivotForest = (dossiers: Dossier[], language: 'en' | 'fr' = 'en'): MenuPathNode[] => {
  const group = getGroupPivot(dossiers);
  const nodes: MenuPathNode[] = [];

  if (group[PIVOTS]) {
    nodes.push({
      path: '',
      pivots: sortBy(group[PIVOTS], item => item.pivot.label?.[language]),
      children: []
    });
  }

  nodes.push(...buildPathMap(group, language));

  return nodes;
};
