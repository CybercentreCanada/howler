// eslint-disable-next-line import/no-cycle
import { hdelete, hget, hpost, hput, joinAllUri, joinUri } from 'api';
import { uri as parentUri } from 'api/v2';
import * as items from 'api/v2/case/items';
import * as rules from 'api/v2/case/rules';

import type { Case } from 'models/entities/generated/Case';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'case', id) : joinUri(parentUri(), 'case');
};

export const get = (id: string) => {
  return hget<Case>(uri(id));
};

export const post = (newData: Partial<Case>) => {
  return hpost<Case>(uri(), newData);
};

export const put = (id: string, _case: Partial<Case>) => {
  return hput<Case>(uri(id), _case);
};

export const del = (id: string) => {
  return hdelete(uri(id));
};

export { items, rules };
