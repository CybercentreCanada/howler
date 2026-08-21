import { hpost, joinAllUri } from 'api';
import type { HowlerSearchResponse, HowlerSigmaSearchRequest } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Hit } from 'models/entities/generated/Hit';

export const uri = () => {
  return joinAllUri(parentUri(), 'hit', 'sigma');
};

export const post = (request?: HowlerSigmaSearchRequest) => {
  return hpost<HowlerSearchResponse<Hit>>(uri(), { ...request, sigma: request?.sigma || '' });
};
