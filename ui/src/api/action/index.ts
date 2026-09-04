import {
  hdelete,
  hget,
  hpatch,
  hpost,
  hput,
  joinAllUri,
  joinUri,
  uri as parentUri,
  type HowlerRefreshParam
} from 'api';
import * as execute from 'api/action/execute';
import * as operations from 'api/action/operations';
import type { Action } from 'models/entities/generated/Action';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'action', id) : joinUri(parentUri(), 'action');
};

export const get = (id: string) => {
  return hget<Action>(uri(id));
};

export const post = (data: Action, refresh?: HowlerRefreshParam) => {
  return hpost<Action>(uri(), data, {}, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (id: string, data: Action, refresh?: HowlerRefreshParam) => {
  return hput<Action>(uri(id), data, {}, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const patch = (id: string, data: Action, refresh?: HowlerRefreshParam) => {
  return hpatch<Action>(uri(id), data, {}, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam) => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export { execute, operations };
