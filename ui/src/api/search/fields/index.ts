import { uri as parentUri } from 'api/search';
import * as event from 'api/search/fields/event';
import * as hit from 'api/search/fields/hit';
import * as user from 'api/search/fields/user';
import type { APIIndex } from 'models/entities/generated/ApiType';
import { joinUri } from 'api';

export type SearchField = APIIndex & { key?: string };

export const uri = () => {
  return joinUri(parentUri(), 'fields');
};

export const map = (fields: { [key: string]: SearchField }): SearchField[] => {
  return Object.keys(fields).map(key => ({ ...fields[key], key }));
};

export const indexed = (fields: { [key: string]: SearchField }): SearchField[] => {
  return map(fields).filter(field => field.indexed);
};

export { event, hit, user };
