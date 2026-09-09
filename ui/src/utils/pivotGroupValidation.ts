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

const pivotGroupValidation = (group: string): string | null => {
  if (!group || group === '') return null;

  // Only contain, French, English, numeral character as well as /.
  if (!/^[0-9A-Za-zùûüÿàâæçéèêëïîôœÙÛÜŸÀÂÆÇÉÈÊËÏÎÔŒ/]*$/.test(group)) {
    return 'route.dossiers.pivots.invalid.character';
  }

  // Protection against wrongly formated /. We need words inbetween and they should not start or end with a /.
  if (group.includes('//') || group.startsWith('/') || group.endsWith('/')) {
    return 'route.pivots.groups.invalid.format';
  }

  return null;
};

export default pivotGroupValidation;
