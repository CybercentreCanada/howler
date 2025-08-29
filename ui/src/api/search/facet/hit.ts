import { hpost, joinUri } from 'api';
import type { HowlerFacetSearchRequest, HowlerFacetSearchResponse } from 'api/search/facet';
import { uri as parentUri } from 'api/search/facet';

export const uri = () => {
  return joinUri(parentUri(), 'hit');
};

export const post = (request?: HowlerFacetSearchRequest): Promise<{ [index: string]: HowlerFacetSearchResponse }> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'howler.id:*' });
};
