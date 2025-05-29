import { hget, joinUri } from 'api';
import { uri as parentUri } from 'api/user';

export type GroupDetailsResponse = { id: string; name: string }[];

export const uri = () => {
  return joinUri(parentUri(), 'groups');
};

export const get = (): Promise<GroupDetailsResponse> => {
  return hget(uri());
};
