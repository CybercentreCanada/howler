import { hpost, joinUri } from 'api';
import type { HowlerCountResult, HowlerCountSearchRequest } from 'api/search/count';
import { uri as parentUri } from 'api/search/count';

export const uri = () => {
  return joinUri(parentUri(), 'hit');
};

export const post = (request?: HowlerCountSearchRequest): Promise<HowlerCountResult> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'howler.id:*' });
};
