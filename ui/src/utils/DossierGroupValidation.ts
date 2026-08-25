/**
 * Verify if the given string follow the rules from group. This is the same check as in dossier_service.py
 * @param group requested path for Dossier
 *
 *
 * @returns null if valid, path to the error if invalid
 */

const DossierGroupValidation = (group: string): string | null => {
  if (!group || group === '') return null;

  const validationRegex = /^[1-9A-Za-zùûüÿàâæçéèêëïîôœÙÛÜŸÀÂÆÇÉÈÊËÏÎÔŒ/]*$/;
  const not_allowed_word = /(^|\/)pivot(\/|$)/;

  if (!validationRegex.test(group)) {
    return 'route.pivots.groups.invalid.character';
  }
  if (not_allowed_word.test(group)) {
    return 'route.pivots.groups.invalid.word';
  }
  if (group.includes('//') || group.startsWith('/') || group.endsWith('/')) {
    return 'route.pivots.groups.invalid.format';
  }

  return null;
};

export default DossierGroupValidation;
