/* eslint-disable import/no-cycle */
import { hget, joinAllUri } from 'api';
import type { Dossier } from 'models/entities/generated/Dossier';
import { uri as parentUri } from '.';

const uri = (id: string) => joinAllUri(parentUri(), 'hit', id);

export const get = (id?: string): Promise<Dossier[]> => {
  return hget(uri(id));
};
