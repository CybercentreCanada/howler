import { hget, joinUri } from 'api';
import { uri as parentUri } from 'api/user';
import type { HowlerUser } from 'models/entities/HowlerUser';

export const uri = () => {
  return joinUri(parentUri(), 'whoami');
};

export const get = (): Promise<HowlerUser> => {
  return hget(uri());
};
