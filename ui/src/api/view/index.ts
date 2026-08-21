import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as favourite from 'api/view/favourite';
import type { View } from 'models/entities/generated/View';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'view', id) : joinUri(parentUri(), 'view');
};

export const get = () => {
  return hget<View[]>(uri());
};

export const post = (newData: Partial<View>, refresh?: HowlerRefreshParam) => {
  return hpost<View>(uri(), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (id: string, partialView: Partial<Omit<View, 'view_id'>>, refresh?: HowlerRefreshParam) => {
  return hput<View>(uri(id), partialView, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam) => {
  return hdelete<void>(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export { favourite };
