import { joinUri, uri as parentUri } from 'api';
import * as action from 'api/search/action';
import * as analytic from 'api/search/analytic';
import * as count from 'api/search/count';
import * as dossier from 'api/search/dossier';
import * as facet from 'api/search/facet';
import * as fields from 'api/search/fields';
import * as grouped from 'api/search/grouped';
import * as histogram from 'api/search/histogram';
import * as hit from 'api/search/hit';
import * as overview from 'api/search/overview';
import * as template from 'api/search/template';
import * as user from 'api/search/user';
import * as view from 'api/search/view';

export const uri = () => {
  return joinUri(parentUri(), 'search');
};

export type HowlerSearchRequest = {
  query: string;
  rows?: number;
  offset?: number;
  sort?: string;
  track_total_hits?: boolean;
  fl?: string;
  timeout?: number;
  filters?: string[];
  metadata?: string[];
};

export type HowlerSearchResponse<T> = {
  items: T[];
  offset: number;
  rows: number;
  total: number;
};

export type HowlerEQLSearchResponse<T> = {
  items: T[];
  sequences: T[][];
  offset: number;
  rows: number;
  total: number;
};

export type HowlerEQLSearchRequest = {
  eql_query: string;
  rows?: number;
  fl?: string;
  timeout?: number;
  filters?: string[];
};

export type HowlerSigmaSearchRequest = {
  sigma: string;
  rows?: number;
  fl?: string;
  timeout?: number;
  filters?: string[];
};

export type HowlerExplainSearchRequest = {
  query: string;
};

export type HowlerExplainSearchResponse = {
  valid: boolean;
  explanations: { valid: boolean; explanation: string }[];
};

export { action, analytic, count, dossier, facet, fields, grouped, histogram, hit, overview, template, user, view };
