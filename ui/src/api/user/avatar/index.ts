import { hget, joinUri } from 'api';
import { uri as parentUri } from 'api/user';

export const uri = (username: string) => {
  return joinUri(joinUri(parentUri(), 'avatar'), username);
};

export const get = (username: string) => {
  return hget<string>(uri(username));
};
