import { hdelete, hget, hpost, hput, joinAllUri, joinUri, uri as parentUri } from 'api';
import type { Template } from 'models/entities/generated/Template';

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'template', id) : joinUri(parentUri(), 'template');
};

export const get = (): Promise<Template[]> => {
  return hget(uri());
};

export const post = (newData: Template): Promise<Template> => {
  return hpost(uri(), newData);
};

export const put = (id: string, template: Partial<Template>): Promise<Template> => {
  return hput(uri(id), template);
};

export const del = (id: string): Promise<void> => {
  return hdelete(uri(id));
};
