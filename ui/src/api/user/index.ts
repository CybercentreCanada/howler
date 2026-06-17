import { hget, hput, joinUri, uri as parentUri } from 'api';
import * as avatar from 'api/user/avatar';
import * as groups from 'api/user/groups';
import * as whoami from 'api/user/whoami';
import type { HowlerUser } from 'models/entities/HowlerUser';

export const uri = (username?: string) => {
  const _uri = joinUri(parentUri(), 'user');
  return username ? joinUri(_uri, username) : _uri;
};

export const get = (username: string): Promise<HowlerUser> => {
  return hget(uri(username));
};

export const put = (username: string, newData: Partial<HowlerUser> | { new_pass: string }) => {
  return hput(uri(username), newData);
};

export const search = (query: string) => {
  const params = new URLSearchParams({ query });

  return hget(joinUri(parentUri(), 'user/search'), params as any);
};

export { avatar, groups, whoami };
