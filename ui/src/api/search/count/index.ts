import { joinUri } from 'api';
import { uri as parentUri } from 'api/search';
import * as hit from 'api/search/count/hit';

export interface HowlerCountSearchRequest {
  query: string;
  filters?: string[];
}

export interface HowlerCountResult {
  count: number;
}

export const uri = () => {
  return joinUri(parentUri(), 'count');
};

export { hit };
