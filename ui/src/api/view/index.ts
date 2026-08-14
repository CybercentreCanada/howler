import api, { hdelete, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as favourite from 'api/view/favourite';
import type { View } from 'models/entities/generated/View';
import { createPermissionApi } from '../permission';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'view', id) : joinUri(parentUri(), 'view');
};

export const get = async (view_id?: string): Promise<View[]> => {
  const view = await api.search.view.post({ query: `view_id:${view_id}`, rows: 1 });

  return view.items;
};

export const post = (newData: Partial<View>, refresh?: HowlerRefreshParam): Promise<View> => {
  return hpost(uri(), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (
  id: string,
  partialView: Partial<Omit<View, 'view_id'>>,
  refresh?: HowlerRefreshParam
): Promise<View> => {
  return hput(uri(id), partialView, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const del = (id: string, refresh?: HowlerRefreshParam): Promise<void> => {
  return hdelete(uri(id), undefined, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const permission = createPermissionApi<View>(uri);

export { favourite };
