import { hpost, joinAllUri } from 'api';
import { uri as parentUri } from 'api/analytic';
import type { Analytic } from 'models/entities/generated/Analytic';

export const uri = (id: string) => {
  return joinAllUri(parentUri(), id, 'owner');
};

export const post = (id: string, body: { username: string }): Promise<Analytic> => {
  return hpost(uri(id), body);
};
