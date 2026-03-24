// eslint-disable-next-line import/no-cycle
import { hdelete, hpost, joinAllUri, joinUri } from 'api';
import { uri as parentUri } from 'api/v2/case';

import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';

export const uri = (id: string, value?: string) => {
  return !value ? joinUri(parentUri(id), 'items') : joinAllUri(parentUri(id), 'items', value);
};

export const post = (id: string, newData: Item): Promise<Case> => {
  return hpost(uri(id), newData);
};

export const del = (id: string, value: string): Promise<void> => {
  return hdelete(uri(id, value));
};
