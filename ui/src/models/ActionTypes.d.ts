import type { Action } from './entities/generated/Action';
import type { Operation } from './entities/generated/Operation';

export type ActionTrigger = NonNullable<Action['triggers']>[number];

export interface ActionOperationStep {
  args: {
    [index: string]: string[];
  };
  optional_args?: string[];
  options: {
    [index: string]: string[] | { [index: string]: string[] };
  };
  validation: {
    warn?: {
      query: string;
      message?: string;
    };
    error?: {
      query: string;
      message?: string;
    };
  };
}

export interface ActionOperation {
  id: string;
  title: string;
  i18nKey: string;
  description: {
    short: string;
    long: string;
  };
  roles: string[];
  steps: ActionOperationStep[];
  triggers: ActionTrigger[];
  priority?: number;
}

export interface ActionRequest {
  request_id: string;
  action_id?: string;
  query?: string;
  operations?: Operation[];
}

export interface ActionReport {
  [index: string]: {
    query: string;
    outcome: 'success' | 'error' | 'skipped';
    title: string;
    message: string;
  }[];
}
