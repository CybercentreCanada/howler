import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Hit } from 'models/entities/generated/Hit';

import * as eql from 'api/search/eql/hit';
import * as sigma from 'api/search/sigma/hit';

export const uri = () => {
  return joinUri(parentUri(), 'hit');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<Hit>> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'howler.id:*' });
};

export { eql, sigma };
