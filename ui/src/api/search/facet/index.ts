import { joinUri } from 'api';
import { uri as parentUri } from 'api/search';
import * as hit from 'api/search/facet/hit';

export const uri = () => {
  return joinUri(parentUri(), 'facet');
};

export type HowlerFacetSearchRequest = {
  fields?: string[];
  query?: string;
  mincount?: number;
  rows?: number;
  filters?: string[];
};

export type HowlerFacetSearchResponse = { [field: string]: { [value: string]: number } };

export { hit };
