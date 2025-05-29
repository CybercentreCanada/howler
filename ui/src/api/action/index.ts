import { hdelete, hpatch, hpost, hput, joinAllUri, joinUri, uri as parentUri } from 'api';
import * as execute from 'api/action/execute';
import * as operations from 'api/action/operations';
import { action } from 'api/search';
import type { Action } from 'models/entities/generated/Action';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'action', id) : joinUri(parentUri(), 'action');
};

export const get = (id: string): Promise<Action> => {
  return action
    .post({
      query: `action_id:${id}`,
      rows: 1
    })
    .then(res => res.items[0]);
};

export const post = (data: Action): Promise<Action> => {
  return hpost(uri(), data);
};

export const put = (id: string, data: Action): Promise<Action> => {
  return hput(uri(id), data);
};

export const patch = (id: string, data: Action): Promise<Action> => {
  return hpatch(uri(id), data);
};

export const del = (id: string): Promise<void> => {
  return hdelete(uri(id));
};

export { execute, operations };
