import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Case } from 'models/entities/generated/Case';

export const uri = () => {
  return joinUri(parentUri(), 'case');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<Case>> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'case_id:*' });
};
