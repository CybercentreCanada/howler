import { hpost, joinUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/search';
import type { Template } from 'models/entities/generated/Template';

export const uri = () => {
  return joinUri(parentUri(), 'template');
};

export const post = (request?: HowlerSearchRequest) => {
  return hpost<HowlerSearchResponse<Template>>(uri(), { ...request, query: request?.query || 'template_id:*' });
};
