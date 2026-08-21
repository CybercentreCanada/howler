import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { View } from 'models/entities/generated/View';

export const uri = () => {
  return joinUri(parentUri(), 'view');
};

export const post = (request?: HowlerSearchRequest) => {
  return hpost<HowlerSearchResponse<View>>(uri(), { ...request, query: request?.query || 'title:*' });
};
