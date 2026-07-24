import { hput, joinAllUri } from 'api';
import type { HitActionResponse } from 'api/hit';
import { uri as parentUri } from 'api/hit';

interface AssignBody {
  value: string | null;
}

export const uri = (id: string) => {
  return joinAllUri(parentUri(), id, 'assign');
};

export const put = (id: string, body: AssignBody) => {
  return hput<HitActionResponse>(uri(id), body);
};
