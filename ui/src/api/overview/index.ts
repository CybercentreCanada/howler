import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import type { Overview } from 'models/entities/generated/Overview';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'overview', id) : joinUri(parentUri(), 'overview');
};

export const get = () => {
  return hget<Overview[]>(uri());
};

export const post = (newData: Partial<Overview>, refresh?: HowlerRefreshParam) => {
  return hpost<Overview>(uri(), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (id: string, content: string, refresh?: HowlerRefreshParam) => {
  return hput<Overview>(uri(id), { content }, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam) => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};
