import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { View } from 'models/entities/generated/View';

export const uri = () => {
  return joinUri(parentUri(), 'view');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<View>> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'title:*' });
};
