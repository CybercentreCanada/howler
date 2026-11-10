import { hpost, joinAllUri } from 'api';
import type { Notification } from 'api/v2/notification';
import { uri as parentUri } from 'api/v2/notification';

export const uri = (id: string) => joinAllUri(parentUri(), id, 'read');

export const post = (id: string) => {
  return hpost<Notification>(uri(id), null);
};
