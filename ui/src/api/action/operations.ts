import { hget, joinUri } from 'api';
import { uri as parentUri } from 'api/action';
import type { ActionOperation } from 'models/ActionTypes';

export const uri = () => {
  return joinUri(parentUri(), 'operations');
};

export const get = async () => {
  return (await hget<ActionOperation[]>(uri())) ?? [];
};
