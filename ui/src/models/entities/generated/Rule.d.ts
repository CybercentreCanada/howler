/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Rule {
  rule_id?: string;
  destination?: string;
  query?: string;
  author?: string;
  enabled?: boolean;
  created_at?: string;
  timeframe?: number;
  expire_after_resolved?: boolean;
  indexes?: ('hit' | 'event')[];
}
