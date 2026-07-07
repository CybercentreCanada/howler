// eslint-disable-next-line import/no-cycle
import { hdelete, hpost, hput, joinUri } from 'api';
import { uri as parentUri } from 'api/v2/case';

import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';

export const uri = (id: string) => {
  return joinUri(parentUri(id), 'items');
};

export const post = (id: string, newData: Item): Promise<Case> => {
  return hpost(uri(id), newData);
};

export const del = (id: string, ids: string[], force = false): Promise<Case> => {
  return hdelete(uri(id), { ids, force });
};

export const move = (id: string, itemId: string, newParent: string | null): Promise<Case> => {
  return hput(uri(id), { id: itemId, new_parent: newParent });
};

export const rename = (id: string, itemId: string, newName: string): Promise<Case> => {
  return hput(uri(id), { id: itemId, new_name: newName });
};
