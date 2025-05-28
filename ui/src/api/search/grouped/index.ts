import { joinUri } from 'api';
import { uri as parentUri } from 'api/search';
import * as hit from 'api/search/grouped/hit';
import * as user from 'api/search/grouped/user';

export const uri = () => {
  return joinUri(parentUri(), 'grouped');
};

export type HowlerGroupedSearchRequest = {
  group_sort?: string;
  limit?: number;
  query?: string;
  offset?: number;
  rows?: number;
  sort?: string;
  fl?: string;
  filters?: string[];
};

type GroupedResult<T> = {
  value: string;
  total: number;
  items: T[];
};

export type HowlerGroupedSearchResponse<T> = {
  items: GroupedResult<T>[];
  offset: number;
  rows: number;
  total: number;
};

export { hit, user };
