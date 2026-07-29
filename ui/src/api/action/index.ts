import { hdelete, hpatch, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as execute from 'api/action/execute';
import * as operations from 'api/action/operations';
import { action } from 'api/search';
import type { Action } from 'models/entities/generated/Action';
import createPermissionsApi from '../utils/createPermissionsApi';

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

export const post = (data: Action, refresh?: HowlerRefreshParam): Promise<Action> => {
  return hpost(uri(), data, {}, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (id: string, data: Action, refresh?: HowlerRefreshParam): Promise<Action> => {
  return hput(uri(id), data, {}, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const patch = (id: string, data: Action, refresh?: HowlerRefreshParam): Promise<Action> => {
  return hpatch(uri(id), data, {}, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam): Promise<void> => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

const permission = createPermissionsApi<Action>(uri);

export { execute, operations, permission };
