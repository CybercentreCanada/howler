import type { ClassificationDefinition } from 'utils/classificationParser';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface APIIndex {
  default: boolean;
  indexed: boolean;
  list: boolean;
  stored: boolean;
  deprecated: boolean;
  type: string;
  description: string;
  regex: string;
  values: string[];
  deprecated_description: string;
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
  'howler.status': ['open', 'in-progress', 'on-hold', 'resolved'];
  'howler.scrutiny': ['unseen', 'surveyed', 'scanned', 'inspected', 'investigated'];
  'howler.escalation': ['miss', 'hit', 'alert', 'evidence'];
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
  'case.escalation': ["normal", "focus", "crisis"];
  transitions: { [index: string]: string[] };
  techniques: { [index: string]: { key: string; name: string; url: string } };
  tactics: { [index: string]: { key: string; name: string; url: string } };
  icons: string[];
  roles: ['admin', 'actionrunner_advanced', 'actionrunner_basic', 'automation_advanced', 'automation_basic', 'user'];
}

export interface APIConfiguration extends APIMappings {
  auth: {
    allow_apikeys: boolean;
    allow_extended_apikeys: boolean;
    max_apikey_duration_amount?: number;
    max_apikey_duration_unit?: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years';
    oauth_providers: string[];
    internal: {
      enabled: boolean;
    };
  };
  system: {
    type: string;
    version: string;
    branch: string;
    commit: string;
    retention: {
      enabled: boolean;
      limit_unit: string;
      limit_amount: number;
    };
  };
  ui: {
    apps: { alt: string; name: string; img_d: string; img_l: string; route: string; classification: string }[];
  };
  features: {
    clue: boolean;
    notebook: boolean;
    [feature: string]: boolean;
  };
  clue: {
    status_checks: string[];
  };
}

export interface APIC12Ndef extends ClassificationDefinition {}

export interface APIMappings {
  mapping: { [index: string]: string };
}

export interface ApiType {
  indexes: APIIndexes;
  lookups: APILookups;
  configuration: APIConfiguration;
  c12nDef: ClassificationDefinition;
}
