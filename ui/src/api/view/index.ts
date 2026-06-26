import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as favourite from 'api/view/favourite';
import type { View } from 'models/entities/generated/View';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'view', id) : joinUri(parentUri(), 'view');
};

export const get = async (view_id?: string): Promise<any> => {
  if (view_id) {
    const views = await hget(uri());
    return views.find((v: any) => v.view_id === view_id || v.id === view_id) || null;
  }
  return hget(uri());
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

export const permission = {
  put: (view_id: string, data: { privilege: string; user_id: string }) => {
    return hput(joinAllUri(uri(view_id), 'permission'), data);
  },

  delete: (view_id: string, data: { privilege: string; user_id: string }) => {
    return hdelete(joinAllUri(uri(view_id), 'permission'), data);
  },

  getOptions: (view_id: string) => {
    return hget(joinAllUri(uri(view_id), 'permission_options'));
  },

  getMembers: (id: string) => {
    return hget(joinAllUri(uri(id), 'permission_options'));
  }
};

export { favourite };
