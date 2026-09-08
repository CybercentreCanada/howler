import type { Case } from 'models/entities/generated/Case';

export const buildPathFromID = (_case: Case, itemId: string): string => {
  const item = _case.items?.find(i => i.id === itemId);
  if (!item) {
    return itemId;
  }

  const name = item.name ?? item.value ?? itemId;
  if (!item.parent) {
    return name;
  }

  const parentPath = buildPathFromID(_case, item.parent);
  return `${parentPath}/${name}`;
};
