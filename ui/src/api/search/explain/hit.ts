import { hpost, joinAllUri } from 'api';
import type { HowlerExplainSearchRequest, HowlerExplainSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';

export const uri = () => {
  return joinAllUri(parentUri(), 'hit', 'explain');
};

export const post = (request?: HowlerExplainSearchRequest): Promise<HowlerExplainSearchResponse> => {
  return hpost(uri(), { ...(request || {}), eql_query: request?.query || 'howler.id:*' });
};
