import { hput, joinAllUri, type HowlerRefreshParam } from 'api';
import { uri as parentUri } from 'api/hit';
import type { Hit } from 'models/entities/generated/Hit';

export const uri = (id: string) => {
  return joinAllUri(parentUri(), id, 'overwrite');
};

export const put = <T extends Hit = Hit>(id: string, body: Partial<T>, refresh?: HowlerRefreshParam) => {
  return hput<T>(uri(id), body, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};
