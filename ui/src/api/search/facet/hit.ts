import { hpost, joinAllUri } from 'api';
import type { HowlerFacetSearchRequest, HowlerFacetSearchResponse } from 'api/search/facet';
import { uri as parentUri } from 'api/search/facet';

export const uri = (field: string) => {
  return joinAllUri(parentUri(), 'hit', field);
};

export const post = (field: string, request?: HowlerFacetSearchRequest): Promise<HowlerFacetSearchResponse> => {
  return hpost(uri(field), { ...(request || {}), query: request?.query || 'howler.id:*' });
};
