// eslint-disable-next-line import/no-cycle
import { hdelete, hget, hpost, hput, joinAllUri, joinUri } from 'api';
import { uri as parentUri } from 'api/v2';
import * as items from 'api/v2/case/items';

import type { Case } from 'models/entities/generated/Case';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'case', id) : joinUri(parentUri(), 'case');
};

export const get = (id: string): Promise<Case> => {
  return hget(uri(id));
};

export const post = (newData: Partial<Case>): Promise<Case> => {
  return hpost(uri(), newData);
};

export const put = (id: string, _case: Partial<Case>): Promise<Case> => {
  return hput(uri(id), _case);
};

export const del = (id: string): Promise<void> => {
  return hdelete(uri(id));
};

export { items };
