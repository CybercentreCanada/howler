import { hpost, joinAllUri } from 'api';
import type { HitTransitionBody } from 'api/hit';
import { uri as parentUri } from 'api/hit';
import type { Hit } from 'models/entities/generated/Hit';

export const uri = (id: string) => {
  return joinAllUri(parentUri(), id, 'transition');
};

export const post = (id: string, body: HitTransitionBody): Promise<Hit> => {
  return hpost(uri(id), body);
};
