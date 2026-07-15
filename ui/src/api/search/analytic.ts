import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Analytic } from 'models/entities/generated/Analytic';

export const uri = () => {
  return joinUri(parentUri(), 'analytic');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<Analytic>> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'analytic_id:*' });
};
