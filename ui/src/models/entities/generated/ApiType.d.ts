import type { ClassificationDefinition } from 'utils/classificationParser';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface APIIndex {
  default: boolean;
  deprecated: boolean;
  deprecated_description: string;
  description: string;
  indexed: boolean;
  list: boolean;
  regex: string;
  stored: boolean;
  type: string;
  values: string[];
}

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface APIIndexes {
  action: { [index: string]: APIIndex };
  analytic: { [index: string]: APIIndex };
  case: { [index: string]: APIIndex };
  dossier: { [index: string]: APIIndex };
  event: { [index: string]: APIIndex };
  hit: { [index: string]: APIIndex };
  overview: { [index: string]: APIIndex };
  template: { [index: string]: APIIndex };
  user: { [index: string]: APIIndex };
  view: { [index: string]: APIIndex };
}

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface APILookups {
  'case.escalation': ['normal', 'focus', 'crisis'];
  'howler.assessment': [
    'ambiguous',
    'security',
    'development',
    'false-positive',
    'legitimate',
    'trivial',
    'recon',
    'attempt',
    'compromise',
    'mitigated'
  ];
  'howler.escalation': ['miss', 'hit', 'alert', 'evidence'];
  'howler.scrutiny': ['unseen', 'surveyed', 'scanned', 'inspected', 'investigated'];
  'howler.status': ['open', 'in-progress', 'on-hold', 'resolved'];
  icons: string[];
  roles: [
    'actionrunner_advanced',
    'actionrunner_basic',
    'admin',
    'automation_advanced',
    'automation_basic',
    'user'
  ];
  tactics: { [index: string]: { key: string; name: string; url: string } };
  techniques: { [index: string]: { key: string; name: string; url: string } };
  transitions: { [index: string]: string[] };
}

export interface APIConfiguration extends APIMappings {
  auth: {
    allow_apikeys: boolean;
    allow_extended_apikeys: boolean;
    internal: {
      enabled: boolean;
    };
    max_apikey_duration_amount?: number;
    max_apikey_duration_unit?: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years';
    oauth_providers: string[];
  };
  clue: {
    status_checks: string[];
  };
  features: {
    ai_lucene: boolean;
    clue: boolean;
    notebook: boolean;
    [feature: string]: boolean;
  };
  system: {
    branch: string;
    commit: string;
    retention: {
      enabled: boolean;
      limit_amount: number;
      limit_unit: string;
    };
    type: string;
    version: string;
  };
  ui: {
    apps: { alt: string; name: string; img_d: string; img_l: string; route: string; classification: string }[];
  };
}

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface APIMappings {
  mapping: { [index: string]: string };
}

export interface ApiType {
  indexes: APIIndexes;
  lookups: APILookups;
  configuration: APIConfiguration;
  c12nDef: ClassificationDefinition;
}
