import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Overview } from 'models/entities/generated/Overview';

export const uri = () => {
  return joinUri(parentUri(), 'overview');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<Overview>> => {
  return hpost(uri(), { ...request, query: request?.query || 'overview_id:*' });
};
