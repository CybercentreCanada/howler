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
  dossier: { [index: string]: APIIndex };
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
  transitions: { [index: string]: string[] };
  tactics: { [index: string]: { key: string; name: string; url: string } };
  techniques: { [index: string]: { key: string; name: string; url: string } };
  icons: string[];
  roles: ['admin', 'automation_advanced', 'automation_basic', 'user'];
}

export interface APIConfiguration {
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
  mapping: APIMappings;
  features: {
    notebook: boolean;
    [feature: string]: boolean;
  };
}

export interface APIC12Ndef {
  levels_map: {
    U: number;
    100: string;
    PA: number;
    110: string;
    PB: number;
    120: string;
    PC: number;
    130: string;
    S: number;
    TS: number;
  };
  levels_map_stl: {
    U: string;
    PA: string;
    PB: string;
    PC: string;
    S: string;
    TS: string;
  };
  levels_map_lts: {
    Unclassified: string;
    'Protected A': string;
    'Protected B': string;
    'Protected C': string;
    Secret: string;
    'Top Secret': string;
  };
  levels_styles_map: {
    U: {
      color: string;
    };
    Unclassified: {
      color: string;
    };
    PA: {
      color: string;
    };
    'Protected A': {
      color: string;
    };
    PB: {
      color: string;
    };
    'Protected B': {
      color: string;
    };
    PC: {
      color: string;
    };
    'Protected C': {
      color: string;
    };
    S: {
      color: string;
    };
    Secret: {
      color: string;
    };
    TS: {
      color: string;
    };
    'Top Secret': {
      color: string;
    };
  };
  levels_aliases: {
    U: string;
    UNCLASSIFIED: string;
    PA: string;
    'PROTECTED A': string;
    PB: string;
    'PROTECTED B': string;
    PC: string;
    'PROTECTED C': string;
    S: string;
    SECRET: string;
    TS: string;
    'TOP SECRET': string;
  };
  access_req_map_lts: {
    'Official Use Only': string;
  };
  access_req_map_stl: {
    OUO: string;
  };
  access_req_aliases: {
    'OFFICIAL USE ONLY': string[];
  };
  groups_map_lts: {};
  groups_map_stl: {};
  groups_aliases: {};
  groups_auto_select: [];
  groups_auto_select_short: [];
  subgroups_map_lts: {};
  subgroups_map_stl: {};
  subgroups_aliases: {};
  subgroups_auto_select: [];
  subgroups_auto_select_short: [];
  params_map: {
    U: {};
    Unclassified: {};
    PA: {};
    'Protected A': {};
    PB: {};
    'Protected B': {};
    PC: {};
    'Protected C': {};
    S: {};
    Secret: {};
    TS: {};
    'Top Secret': {};
    OUO: {};
    'Official Use Only': {};
  };
  description: {
    U: string;
    Unclassified: string;
    PA: string;
    'Protected A': string;
    PB: string;
    'Protected B': string;
    PC: string;
    'Protected C': string;
    S: string;
    Secret: string;
    TS: string;
    'Top Secret': string;
    OUO: string;
    'Official Use Only': string;
  };
  invalid_mode: boolean;
  enforce: boolean;
  dynamic_groups: boolean;
  UNRESTRICTED: string;
  RESTRICTED: string;
}

export interface APIMappings {
  mapping: { [index: string]: string };
}

export interface ApiType {
  indexes: APIIndexes;
  lookups: APILookups;
  configuration: APIConfiguration;
  c12nDef: APIC12Ndef;
  mapping: APIMappings;
}
