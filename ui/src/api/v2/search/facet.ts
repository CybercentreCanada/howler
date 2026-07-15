// eslint-disable-next-line import/no-cycle
import { hpost, joinAllUri } from 'api';
import type { HowlerFacetSearchRequest, HowlerFacetSearchResponse } from 'api/search/facet';
import { uri as parentUri } from 'api/v2';

export const uri = (indexes: string[]) => {
  return joinAllUri(parentUri(), 'search', 'facet', indexes.join(','));
};

export const post = (
  indexes: string | string[],
  request?: HowlerFacetSearchRequest
): Promise<HowlerFacetSearchResponse> => {
  if (typeof indexes === 'string') {
    indexes = indexes.split(',');
  }

  return hpost(uri(indexes), { ...(request || {}), query: request?.query || 'howler.id:*' });
};
