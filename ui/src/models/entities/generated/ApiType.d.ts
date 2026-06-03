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
  values: string;
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

export interface APIConfiguration {
  auth: {
    allow_apikeys: boolean;
    allow_extended_apikeys: boolean;
    internal: {
      enabled: boolean;
    };
    max_apikey_duration_amount: number;
    max_apikey_duration_unit: string;
    oauth_providers: string[];
  };
  clue: {
    status_checks: []
  };
  features: {
    clue: boolean;
    notebook: boolean;
  };
  mapping: {
    'azure.upn': string;
    'destination.address': string;
    'destination.domain': string;
    'destination.ip': string;
    'destination.nat.ip': string;
    'destination.nat.port': string;
    'destination.port': string;
    'destination.user.email': string;
    'dns.answers.name': string;
    'dns.question.registered_domain': string;
    'dns.question.subdomain': string;
    'dns.question.top_level_domain': string;
    'dns.resolved_ip': string;
    'email.attachments.file.hash.md5': string;
    'email.attachments.file.hash.sha256': string;
    'email.bcc.address': string;
    'email.cc.address': string;
    'email.from.address': string;
    'email.parent.bcc.address': string;
    'email.parent.cc.address': string;
    'email.parent.destination': string;
    'email.parent.from.address': string;
    'email.parent.source': string;
    'email.parent.to.address': string;
    'email.reply_to.address': string;
    'email.sender.address': string;
    'email.to.address': string;
    'event.url': string;
    'file.hash.md5': string;
    'file.hash.sha256': string;
    'host.domain': string;
    'host.ip': string;
    'howler.outline.indicators': string;
    'process.parent.parent.user.email': string;
    'process.parent.user.email': string;
    'process.user.email': string;
    'related.ip': string;
    'server.address': string;
    'server.domain': string;
    'server.ip': string;
    'source.address': string;
    'source.domain': string;
    'source.ip': string;
    'source.nat.ip': string;
    'source.nat.port': string;
    'source.port': string;
    'source.user.email': string;
    'threat.indicator.email.address': string;
    'threat.indicator.ip': string;
    'tls.client.ja3': string;
    'tls.server.ja3s': string;
    'url.domain': string;
    'url.port': string;
    'url.registered_domain': string;
    'url.subdomain': string;
    'url.top_level_domain': string;
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
    apps: []
  };
}

export interface APIC12Ndef {
  RESTRICTED: string;
  UNRESTRICTED: string;
  access_req_aliases: {
    GOD: string[];
  };
  access_req_map_lts: {
    ADMIN: string;
    'SUPER USER': string;
  };
  access_req_map_stl: {
    ADM: string;
    SU: string;
  };
  description: {
    ADM: string;
    ADMIN: string;
    D1: string;
    D2: string;
    'DEPARTMENT 1': string;
    'DEPARTMENT 2': string;
    G1: string;
    G2: string;
    'GROUP 1': string;
    'GROUP 2': string;
    R: string;
    RESTRICTED: string;
    SU: string;
    'SUPER USER': string;
    U: string;
    UNRESTRICTED: string;
  };
  dynamic_groups: boolean;
  dynamic_groups_type: string;
  enforce: boolean;
  groups_aliases: {
    ANY: string[];
    DEPTS: string[];
  };
  groups_auto_select: [];
  groups_auto_select_short: [];
  groups_map_lts: {
    'DEPARTMENT 1': string;
    'DEPARTMENT 2': string;
  };
  groups_map_stl: {
    D1: string;
    D2: string;
  };
  invalid_mode: boolean;
  levels_aliases: {
    CLASSIFIED: string;
    'DO NOT LOOK': string;
  };
  levels_map: {
    100: string;
    200: string;
    R: number;
    U: number;
  };
  levels_map_lts: {
    RESTRICTED: string;
    UNRESTRICTED: string;
  };
  levels_map_stl: {
    R: string;
    U: string;
  };
  levels_styles_map: {
    R: {
      banner: string;
      label: string;
      text: string;
    };
    RESTRICTED: {
      banner: string;
      label: string;
      text: string;
    };
    U: {
      banner: string;
      label: string;
      text: string;
    };
    UNRESTRICTED: {
      banner: string;
      label: string;
      text: string;
    };
  };
  params_map: {
    ADM: {};
    ADMIN: {};
    D1: {
      solitary_display_name: string;
    };
    D2: {};
    'DEPARTMENT 1': {
      solitary_display_name: string;
    };
    'DEPARTMENT 2': {};
    G1: {
      limited_to_group: string;
      require_group: string;
    };
    G2: {};
    'GROUP 1': {
      limited_to_group: string;
      require_group: string;
    };
    'GROUP 2': {};
    R: {};
    RESTRICTED: {};
    SU: {
      require_lvl: number;
    };
    'SUPER USER': {
      require_lvl: number;
    };
    U: {};
    UNRESTRICTED: {};
  };
  subgroups_aliases: {};
  subgroups_auto_select: [];
  subgroups_auto_select_short: [];
  subgroups_map_lts: {
    'GROUP 1': string;
    'GROUP 2': string;
  };
  subgroups_map_stl: {
    G1: string;
    G2: string;
  };
}

export interface ApiType {
  indexes: APIIndexes;
  lookups: APILookups;
  configuration: APIConfiguration;
  c12nDef: APIC12Ndef;
}
