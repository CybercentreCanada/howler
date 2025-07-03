import { hget, joinUri } from 'api';
import { uri as parentUri } from 'api/notebook';

export type EnvsResponse = {
  envs: { name: string; url: string; default: boolean; user_interface: string }[];
};

export const uri = () => {
  return joinUri(parentUri(), 'environments');
};

export const get = (): Promise<EnvsResponse> => {
  return hget(uri());
};
