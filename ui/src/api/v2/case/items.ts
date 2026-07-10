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

export const del = (id: string, ids: string | string[], force = false): Promise<Case> => {
  if (!Array.isArray(ids)) {
    ids = [ids];
  }

  return hdelete(uri(id), { ids, force });
};

export const put = (caseId: string, id: string, payload: { name?: string; parent?: string } = {}): Promise<Case> => {
  (payload as Record<string, string>).id = id;

  return hput(uri(caseId), payload);
};
