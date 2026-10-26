import { hget, joinAllUri } from 'api';
import { uri as actionUri } from 'api/action';
import type { ActionRun, ActionRunListQuery, ActionRunListResponse } from 'models/ActionRunTypes';

export const uri = (runId?: string) =>
  runId ? joinAllUri(actionUri(), 'runs', runId) : joinAllUri(actionUri(), 'runs');

export const list = (query: ActionRunListQuery = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.set(key, String(value));
    }
  });

  return hget<ActionRunListResponse>(uri(), searchParams);
};

export const get = (runId: string) => hget<ActionRun>(uri(runId));
