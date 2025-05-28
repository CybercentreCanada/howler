import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri } from 'api';
import type { Overview } from 'models/entities/generated/Overview';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'overview', id) : joinUri(parentUri(), 'overview');
};

export const get = (): Promise<Overview[]> => {
  return hget(uri());
};

export const post = (newData: Partial<Overview>): Promise<Overview> => {
  return hpost(uri(), newData);
};

export const put = (id: string, content: string): Promise<Overview> => {
  return hput(uri(id), { content });
};

export const del = (id: string): Promise<void> => {
  return hdelete(uri(id));
};
