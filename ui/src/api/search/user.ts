import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { HowlerUser } from 'models/entities/HowlerUser';

export type HowlerApiUser = Omit<HowlerUser, 'username'> & { uname: string };

export const uri = () => {
  return joinUri(parentUri(), 'user');
};

export const post = async (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<HowlerUser>> => {
  const response = await hpost<HowlerSearchResponse<HowlerApiUser>>(uri(), {
    ...(request || {}),
    query: request?.query || 'name:*'
  });
  return {
    ...response,
    items: response.items.map((i: HowlerApiUser) => ({ ...i, username: i.uname }))
  };
};
