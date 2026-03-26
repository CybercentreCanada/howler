// eslint-disable-next-line import/no-cycle
import { hdelete, hpost, joinUri } from 'api';
import { uri as parentUri } from 'api/v2/case';

import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';

export const uri = (id: string) => {
  return joinUri(parentUri(id), 'items');
};

export const post = (id: string, newData: Item): Promise<Case> => {
  return hpost(uri(id), newData);
};

export const del = (id: string, values: string[]): Promise<Case> => {
  return hdelete(uri(id), { values });
};
