import { sortBy } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';

/**
 * Builds a menu-oriented forest from dossier pivots.
 *
 * The flow is:
 * 1) Group pivots by their slash-delimited `pivot.group` path.
 * 2) Store pivots at each path node under an internal symbol key.
 * 3) Convert the grouped object into `menuPathNode[]` for UI rendering.
 * 4) Squash non-branching path chains that contain no local pivots so
 *    navigation menus avoid unnecessary empty intermediate levels.
 *
 * The resulting structure is consumed by Hit links/folder components to
 * render root pivots and nested submenu folders consistently.
 */

const PIVOTS = Symbol('pivots');

export type menuPathNode = {
  path: string;
  pivots?: dossierPivot[];
  children?: menuPathNode[];
};

// use here and in PivotFolderMenu to relate the pivot with its dossier at rendering since we do not consider
// dossier in the grouping. But we need to be able to find where it came from to allow the "open dossier" button to work
export type dossierPivot = {
  pivot: Pivot;
  dossier: Dossier;
};

const getDossierPivotKey = ({ pivot, dossier }: dossierPivot): string => JSON.stringify([dossier.dossier_id, pivot]);

type PivotTree = {
  [PIVOTS]?: dossierPivot[];
  [key: string]: PivotTree;
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
const buildPathMap = (tree: PivotTree, language = 'en'): menuPathNode[] => {
  const nodes: menuPathNode[] = [];
  const languageKey = language === 'fr' ? 'fr' : 'en';
  for (const key in tree) {
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
      pivots: sortBy(current[PIVOTS] ?? [], item => item.pivot.label?.[languageKey]),
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
const pivotForest = (dossiers: Dossier[], language = 'en'): menuPathNode[] => {
  const group = getGroupPivot(dossiers);
  const nodes: menuPathNode[] = [];
  const languageKey = language === 'fr' ? 'fr' : 'en';

  if (group[PIVOTS]) {
    nodes.push({
      path: '',
      pivots: sortBy(group[PIVOTS], item => item.pivot.label?.[languageKey]),
      children: []
    });
  }

  nodes.push(...buildPathMap(group, language));

  return nodes;
};

export { getDossierPivotKey };
export default pivotForest;
