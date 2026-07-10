export type ObservableType = 'hash' | 'hosts' | 'ip' | 'user' | 'ids' | 'id' | 'uri' | 'signature';

export type ObservableRole = 'threat' | 'target' | 'indicator';

export interface ObservableSource {
  id: string;
  type: 'hit' | 'observable' | 'case';
  path?: string;
  label?: string;
  escalation?: string;
}

export interface ObservableEntry {
  type: ObservableType;
  value: string;
  /** IDs of the hits/observables this observable was seen in */
  seenIn: string[];
  /** Resolved source metadata for each seenIn item */
  sources?: ObservableSource[];
  /** Classified role of this observable */
  role?: ObservableRole;
}

export type OriginType = 'hit' | 'observable';
