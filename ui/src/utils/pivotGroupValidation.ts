/**
 * Validates a dossier group path using the same rules as the backend service.
 *
 * Rules:
 * - Allows alphabetic characters (including supported accented letters), digits, and '/'.
 * - Rejects any path segment that is exactly "pivot".
 * - Rejects malformed paths: consecutive '/', leading '/', or trailing '/'.
 *
 * @param group Requested pivot group path.
 * @returns null when valid, otherwise the i18n error key describing the failure.
 */

const pivotGroupValidation = (group: string): string | null => {
  if (!group || group === '') return null;

  // Only contain, French, English, numeral character as well as /.
  if (!/^[1-9A-Za-zùûüÿàâæçéèêëïîôœÙÛÜŸÀÂÆÇÉÈÊËÏÎÔŒ/]*$/.test(group)) {
    return 'route.dossiers.pivots.invalid.character';
  }

  // used into the code to split pivot into a forest. This should not be allowed without an update to the pivotForest
  // pivot1, Pivot or anything else then exactly "pivot" is fine.
  // Also if they start classifying pivot as the category pivot not sur why we did the update
  if (/(^|\/)pivot(\/|$)/.test(group)) {
    return 'route.pivots.groups.invalid.word';
  }

  // Protection against wrongly formated /. We need words inbetween and they should not start or end with a /.
  if (group.includes('//') || group.startsWith('/') || group.endsWith('/')) {
    return 'route.pivots.groups.invalid.format';
  }

  return null;
};

export default pivotGroupValidation;
