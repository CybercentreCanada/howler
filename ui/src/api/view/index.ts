import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri } from 'api';
import * as favourite from 'api/view/favourite';
import type { View } from 'models/entities/generated/View';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'view', id) : joinUri(parentUri(), 'view');
};

export const get = (): Promise<View[]> => {
  return hget(uri());
};

export const post = (newData: Partial<View>): Promise<View> => {
  return hpost(uri(), newData);
};

export const put = (id: string, partialView: Partial<Omit<View, 'view_id'>>): Promise<View> => {
  return hput(uri(id), partialView);
};

export const del = (id: string): Promise<void> => {
  return hdelete(uri(id));
};

export { favourite };
