// eslint-disable-next-line import/no-cycle
import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import type { Dossier } from 'models/entities/generated/Dossier';
import * as hit from './hit';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'dossier', id) : joinUri(parentUri(), 'dossier');
};

export const get = (id?: string): Promise<Dossier | Dossier[]> => {
  return hget(uri(id));
};

export const post = (newData: Partial<Dossier>, refresh?: HowlerRefreshParam): Promise<Dossier> => {
  return hpost(uri(), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (id: string, dossier: Partial<Dossier>, refresh?: HowlerRefreshParam): Promise<Dossier> => {
  return hput(uri(id), dossier, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam): Promise<void> => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const permission = {
  put: (id: string, data: { privilege: string; user_id: string }) => {
    return hput(joinAllUri(uri(id), 'permission'), data);
  },
  delete: (id: string, data: { privilege: string; user_id: string }) => {
    return hdelete(joinAllUri(uri(id), 'permission'), data);
  }
};

export { hit };
