import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as favourite from 'api/view/favourite';
import type { View } from 'models/entities/generated/View';

export const uri = (view_id?: string) => {
  return view_id ? joinAllUri(parentUri(), 'view', view_id) : joinUri(parentUri(), 'view');
};

// Core view management endpoints
export const get = async (view_id?: string): Promise<any> => {
  // If an ID is requested, fetch the available views list and extract it
  if (view_id) {
    const views = await hget(uri()); // Hits GET /api/v1/view/
    return views.find((v: any) => v.view_id === view_id || v.id === view_id) || null;
  }

  // Otherwise, return the full list as usual
  return hget(uri());
};

export const post = (newData: Partial<View>, refresh?: HowlerRefreshParam): Promise<View> => {
  return hpost(uri(), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export const put = (view_id: string, partialView: Partial<Omit<View, 'view_id'>>): Promise<View> => {
  return hput(uri(view_id), partialView);
};

export const del = (view_id: string): Promise<void> => {
  return hdelete(uri(view_id));
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
