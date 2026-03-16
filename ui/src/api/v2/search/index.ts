// eslint-disable-next-line import/no-cycle
import { hpost, joinAllUri } from 'api';
import type { HowlerSearchRequest, HowlerSearchResponse } from 'api/search';
import { uri as parentUri } from 'api/v2';
import type { Hit } from 'models/entities/generated/Hit';
import * as facet from './facet';

export const uri = (indexes: string[]) => {
  return joinAllUri(parentUri(), 'search', indexes.join(','));
};

export const post = <T = Hit>(
  indexes: string | string[],
  request?: HowlerSearchRequest
): Promise<HowlerSearchResponse<T>> => {
  if (typeof indexes === 'string') {
    indexes = indexes.split(',');
  }

  if (indexes.some(index => !['hit', 'observable', 'case'].includes(index))) {
    // eslint-disable-next-line no-console
    console.error('Only hit, case and observable indexes should be used currently.');
  }

  return hpost(uri(indexes), { ...(request || {}), query: request?.query || 'howler.id:*' });
};

export { facet };
