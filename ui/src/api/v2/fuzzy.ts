import { hpost, joinAllUri } from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/v2';
import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';

export type FuzzySearchRequest = {
  query: string;
  indexes?: string[];
  filters?: string[];
  offset?: number;
  rows?: number;
  track_total_hits?: boolean;
};

export type FuzzySearchItem<T = Hit | Event | Case> = T & {
  _score: number;
};

export const uri = () => {
  return joinAllUri(parentUri(), 'fuzzy');
};

export const post = (request: FuzzySearchRequest): Promise<HowlerSearchResponse<FuzzySearchItem>> => {
  if (!request.query || !request.query.trim()) {
    throw new Error('Search query is required.');
  }

  return hpost(joinAllUri(uri(), 'search'), request);
};
