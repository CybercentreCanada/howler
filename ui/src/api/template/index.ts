import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import type { Template } from 'models/entities/generated/Template';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'template', id) : joinUri(parentUri(), 'template');
};

export const get = async () => {
  return (await hget<Template[]>(uri())) ?? [];
};

export const post = (newData: Partial<Template>, refresh?: HowlerRefreshParam) => {
  return hpost<Template>(uri(), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (id: string, newFields: string[], refresh?: HowlerRefreshParam) => {
  return hput<Template>(uri(id), newFields, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam) => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};
