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

export const put = (
  id: string,
  title: string,
  query: string,
  sort: string,
  span: string,
  advanceOnTriage: boolean
): Promise<View> => {
  return hput(uri(id), { title, query, sort, span, settings: { advance_on_triage: advanceOnTriage } } as View);
};

export const del = (id: string): Promise<void> => {
  return hdelete(uri(id));
};

export { favourite };
