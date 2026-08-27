import type { SearchField } from 'api/search/fields';
import { indexed, uri as parentUri } from 'api/search/fields';
// import urlJoin from 'url-join';
import { hget, joinUri } from 'api';

export const uri = () => {
  return joinUri(parentUri(), 'user');
};

export const get = async (): Promise<SearchField[]> => {
  return indexed((await hget<{ [key: string]: SearchField }>(uri())) ?? {});
};
