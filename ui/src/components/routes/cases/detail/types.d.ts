export type ObservableType = 'hash' | 'hosts' | 'ip' | 'user' | 'ids' | 'id' | 'uri' | 'signature';

export type ObservableRole = 'threat' | 'target' | 'indicator';

export interface ObservableSource {
  id: string;
  type: 'hit' | 'event' | 'case';
  path?: string;
  label?: string;
  escalation?: string;
}

export interface ObservableEntry {
  type: ObservableType;
  value: string;
  /** Resolved source metadata for each seenIn item */
  sources?: ObservableSource[];
  /** Classified role of this observable */
  role?: ObservableRole;
}

export type OriginType = 'hit' | 'event';
