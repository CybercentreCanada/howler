import { hget, joinUri, uri as parentUri } from 'api';
import type { ApiType } from 'models/entities/generated/ApiType';

export const uri = () => {
  return joinUri(parentUri(), 'configs');
};

export const get = () => {
  return hget<ApiType>(uri());
};
