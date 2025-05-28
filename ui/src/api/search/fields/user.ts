import * as api from 'api';
import type { SearchField } from 'api/search/fields';
import { indexed, uri as parentUri } from 'api/search/fields';
// import urlJoin from 'url-join';
import { joinUri } from 'api';

export const uri = () => {
  return joinUri(parentUri(), 'user');
};

export const get = async (): Promise<SearchField[]> => {
  const response = await api.hget<{ [key: string]: SearchField }>(uri());
  return indexed(response);
};
