import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Template } from 'models/entities/generated/Template';

export const uri = () => {
  return joinUri(parentUri(), 'overview');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<Template>> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'overview_id:*' });
};
