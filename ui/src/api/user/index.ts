import { hget, hput, joinUri, uri as parentUri, type HowlerRefreshParam } from 'api';
import * as avatar from 'api/user/avatar';
import * as groups from 'api/user/groups';
import * as whoami from 'api/user/whoami';
import type { HowlerUser } from 'models/entities/HowlerUser';

export const uri = (username?: string) => {
  const _uri = joinUri(parentUri(), 'user');
  return username ? joinUri(_uri, username) : _uri;
};

export const get = (username: string) => {
  return hget<HowlerUser>(uri(username));
};

export const put = (
  username: string,
  newData: Partial<HowlerUser> | { new_pass: string },
  refresh?: HowlerRefreshParam
) => {
  return hput<HowlerUser>(uri(username), newData, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};

export { avatar, groups, whoami };
