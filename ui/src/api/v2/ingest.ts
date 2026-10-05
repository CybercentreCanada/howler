import { hpost, joinAllUri, type HowlerRefreshParam } from 'api';
import { uri as parentUri } from 'api/v2';

export const uri = (index: string) => {
  return joinAllUri(parentUri(), 'ingest', index);
};

export const post = (index: string, records: Record<string, unknown>[], refresh?: HowlerRefreshParam) => {
  return hpost<string[]>(uri(index), records, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};
