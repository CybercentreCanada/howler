import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri } from 'api';
import type { Template } from 'models/entities/generated/Template';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'template', id) : joinUri(parentUri(), 'template');
};

export const get = (): Promise<Template[]> => {
  return hget(uri());
};

export const post = (newData: Partial<Template>): Promise<Template> => {
  return hpost(uri(), newData);
};

export const put = (id: string, newFields: string[]): Promise<Template> => {
  return hput(uri(id), newFields);
};

export const del = (id: string, wait?: boolean): Promise<void> => {
  const params = new URLSearchParams();
  if (wait) {
    params.append('wait', 'true');
  }
  return hdelete(uri(id), undefined, undefined, params);
};
