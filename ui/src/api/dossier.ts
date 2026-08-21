// eslint-disable-next-line import/no-cycle
import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import type { Dossier } from 'models/entities/generated/Dossier';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'dossier', id) : joinUri(parentUri(), 'dossier');
};

export const get = ((id?: string) => {
  return id ? hget<Dossier>(uri(id)) : hget<Dossier[]>(uri());
}) as {
  (id: string): ReturnType<typeof hget<Dossier>>;
  (id?: undefined): ReturnType<typeof hget<Dossier[]>>;
};

export const post = (newData: Partial<Dossier>, refresh?: HowlerRefreshParam) => {
  return hpost<Dossier>(uri(), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (id: string, dossier: Partial<Dossier>, refresh?: HowlerRefreshParam) => {
  return hput<Dossier>(uri(id), dossier, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam) => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};
