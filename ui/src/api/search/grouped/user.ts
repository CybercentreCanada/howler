import { hpost, joinAllUri } from 'api';
import type { HowlerGroupedSearchRequest, HowlerGroupedSearchResponse } from 'api/search/grouped';
import { uri as parentUri } from 'api/search/grouped';
import type { HowlerUser } from 'models/entities/HowlerUser';

export type HowlerApiUser = Omit<HowlerUser, 'username'> & { uname: string };

export const uri = (field: string) => {
  return joinAllUri(parentUri(), 'user', field);
};

export const post = async (
  field: string,
  body?: HowlerGroupedSearchRequest
): Promise<HowlerGroupedSearchResponse<HowlerUser>> => {
  const response = await hpost<HowlerGroupedSearchResponse<HowlerApiUser>>(uri(field), {
    ...(body || {}),
    query: body?.query || 'uname:*'
  });
  return {
    ...response,
    items: response.items.map(i => ({
      ...i,
      items: i.items.map(_i => ({
        ..._i,
        username: _i.uname
      }))
    }))
  };
};
