// eslint-disable-next-line import/no-cycle
import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri } from 'api';
import type { Dossier } from 'models/entities/generated/Dossier';
import * as hit from './hit';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'dossier', id) : joinUri(parentUri(), 'dossier');
};

export const get = (id?: string): Promise<Dossier | Dossier[]> => {
  return hget(uri(id));
};

export const post = (newData: Partial<Dossier>): Promise<Dossier> => {
  return hpost(uri(), newData);
};

export const put = (id: string, dossier: Partial<Dossier>): Promise<Dossier> => {
  return hput(uri(id), dossier);
};

export const del = (id: string): Promise<void> => {
  return hdelete(uri(id));
};

export const permission = {
  put: (id: string, data: { privilege: string; user_id: string }) => {
    return hput(joinAllUri(uri(id), 'permission'), data);
  },
  delete: (id: string, data: { privilege: string; user_id: string }) => {
    // REMOVE the { data } wrapper so it is just 'data'
    return hdelete(joinAllUri(uri(id), 'permission'), data);
  },
  getOptions: (id: string) => {
    return hget(joinAllUri(uri(id), 'permission_options'));
  }
};

export { hit };
