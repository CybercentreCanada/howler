import { hget, joinUri } from 'api';
import { uri as parentUri } from 'api/user';

export type GroupDetailsResponse = { id: string; name: string }[];

export const uri = () => {
  return joinUri(parentUri(), 'groups');
};

export const get = () => {
  return hget<GroupDetailsResponse>(uri());
};
