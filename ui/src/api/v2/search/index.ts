// eslint-disable-next-line import/no-cycle
import { hpost, joinAllUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/v2';
import { identity, isNil } from 'lodash-es';
import * as facet from './facet';

export type SearchIndex = 'hit' | 'event' | 'case';

export const uri = (indexes: string[]) => {
  return joinAllUri(parentUri(), 'search', indexes.join(','));
};

export const post = <T = any>(
  indexes: SearchIndex | SearchIndex[],
  request?: HowlerSearchRequest
): Promise<HowlerSearchResponse<T>> => {
  if (isNil(indexes)) {
    throw new Error('Indexes cannot be null or undefined.');
  }

  if (typeof indexes === 'string') {
    indexes = indexes.split(',').filter(identity) as SearchIndex[];
  }

  if (indexes.some(index => !['hit', 'event', 'case'].includes(index))) {
    throw new Error('Only hit, case, and event indexes should be used currently.');
  }

  if (indexes.length < 1) {
    throw new Error('indexes must have length of at least 1.');
  }

  return hpost(uri(indexes), { ...(request || {}), query: request?.query || 'howler.id:*' });
};

export { facet };
