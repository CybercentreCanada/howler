// eslint-disable-next-line import/no-cycle
import { hget, joinUri } from 'api';
import { uri as parentUri } from 'api/v2';

import type { Case } from 'models/entities/generated/Case';
import type { Task } from 'models/entities/generated/Task';

export type TaskSearchFilter = 'all' | 'complete' | 'incomplete';

export interface TaskSearchRequest {
  offset: number;
  rows: number;
  filter: TaskSearchFilter;
}

export interface TaskSearchItem {
  task: Task;
  case: Case;
}

export interface TaskSearchResponse {
  items: TaskSearchItem[];
  offset: number;
  rows: number;
  has_more: boolean;
}

export const uri = () => joinUri(joinUri(parentUri(), 'task'), 'search');

export const search = (request: TaskSearchRequest, signal?: AbortSignal) => {
  const params = new URLSearchParams({
    offset: String(request.offset),
    rows: String(request.rows),
    filter: request.filter
  });

  return hget<TaskSearchResponse>(uri(), params, undefined, signal);
};
