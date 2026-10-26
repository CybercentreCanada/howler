export type ActionRunState = 'queued' | 'running' | 'completed';

export type ActionRunResultState = 'queued' | 'running' | 'succeeded' | 'failed' | 'skipped';

export interface ActionRunCounts {
  total: number;
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  skipped: number;
}

export interface ActionRunSummary {
  run_id: string;
  operation_id: 'ai_triage';
  request_id: string | null;
  action_id: string | null;
  trigger: string | null;
  state: ActionRunState;
  revision: number;
  created_at: string;
  started_at: string | null;
  updated_at: string;
  finished_at: string | null;
  expires_at: string | null;
  counts: ActionRunCounts;
}

export interface ActionRunResult {
  hit_id: string;
  state: ActionRunResultState;
  attempts: number;
  reason: string | null;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ActionRun extends ActionRunSummary {
  results: ActionRunResult[];
}

export interface ActionRunListResponse {
  items: ActionRunSummary[];
  offset: number;
  rows: number;
  has_more: boolean;
}

export interface ActionRunListQuery {
  operation_id?: 'ai_triage';
  action_id?: string;
  request_id?: string;
  offset?: number;
  rows?: number;
}
