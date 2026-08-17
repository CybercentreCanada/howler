/**
 * Verify if the given string follow the rules from group. This is the same check as in dossier_service.py
 * @param group requested path for Dossier
 *
 *
 * @returns null if valid, path to the error if invalid
 */

const DossierGroupValidation = (group: string): string | null => {
  if (!group) return null;

  const validationRegex = /^[A-Za-zùûüÿàâæçéèêëïîôœÙÛÜŸÀÂÆÇÉÈÊËÏÎÔŒ/]*$/;

  if (!validationRegex.test(group)) {
    return 'route.dossiers.groups.invalid.character';
  }
  if (group.includes('//') || group.startsWith('/') || group.endsWith('/')) {
    return 'route.dossiers.groups.invalid.format';
  }

  return null;
};

export default DossierGroupValidation;
