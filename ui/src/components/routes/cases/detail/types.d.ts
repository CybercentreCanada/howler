export type AssetType = 'hash' | 'hosts' | 'ip' | 'user' | 'ids' | 'id' | 'uri' | 'signature';

export type AssetRole = 'threat' | 'target' | 'indicator';

export interface AssetSource {
  id: string;
  type: 'hit' | 'observable' | 'case';
  path?: string;
  escalation?: string;
}

export interface AssetEntry {
  type: AssetType;
  value: string;
  /** IDs of the hits/observables this asset was seen in */
  seenIn: string[];
  /** Resolved source metadata for each seenIn item */
  sources?: AssetSource[];
  /** Classified role of this asset */
  role?: AssetRole;
}

export type OriginType = 'hit' | 'observable';
