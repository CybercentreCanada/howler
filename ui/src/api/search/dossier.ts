import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Dossier } from 'models/entities/generated/Dossier';

export const uri = () => {
  return joinUri(parentUri(), 'dossier');
};

export const post = (request?: HowlerSearchRequest): Promise<HowlerSearchResponse<Dossier>> => {
  return hpost(uri(), { ...(request || {}), query: request?.query || 'title:*' });
};
