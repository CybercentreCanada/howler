import { joinUri } from 'api';
import { uri as parentUri } from 'api/search';
import * as hit from 'api/search/histogram/hit';

export const uri = () => {
  return joinUri(parentUri(), 'histogram');
};

export type HowlerHistogramSearchRequest = {
  query?: string;
  mincount?: number;
  filters?: string[];
  start?: string | number;
  end?: string | number;
  gap?: string | number;
};

export type HowlerHistogramSearchResponse = { [timestamp: string]: number };

export { hit };
