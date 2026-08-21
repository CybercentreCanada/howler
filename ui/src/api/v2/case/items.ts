// eslint-disable-next-line import/no-cycle
import { hdelete, hpost, hput, joinUri } from 'api';
import { uri as parentUri } from 'api/v2/case';

import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';

export const uri = (id: string) => {
  return joinUri(parentUri(id), 'items');
};

export const post = (id: string, newData: Item) => {
  return hpost<Case>(uri(id), newData);
};

export const del = (id: string, ids: string | string[], force = false) => {
  if (!Array.isArray(ids)) {
    ids = [ids];
  }

  return hdelete<Case>(uri(id), { ids, force });
};

export const put = (caseId: string, id: string, payload: { name?: string; parent?: string } = {}) => {
  (payload as Record<string, string>).id = id;

  return hput<Case>(uri(caseId), payload);
};
