import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Action } from 'models/entities/generated/Action';

export const uri = () => {
  return joinUri(parentUri(), 'action');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<Action>> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'action_id:*' });
};
