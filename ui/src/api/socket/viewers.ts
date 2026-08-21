import { hget, joinAllUri } from 'api';
import { uri as parentUri } from 'api/socket';

export const uri = (entityId?: string): string => {
  return entityId ? joinAllUri(parentUri(), 'viewers', entityId) : joinAllUri(parentUri(), 'viewers');
};

export const get = (entityId: string) => {
  return hget<string[]>(uri(entityId));
};
