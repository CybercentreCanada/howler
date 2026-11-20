import { hget, joinAllUri } from 'api';
import type { Notification } from 'api/v2/notification';
import { uri as parentUri } from 'api/v2/notification/get';

export interface UserNotificationsRequest {
  offset?: number;
  rows?: number;
}

export interface UserNotificationsResponse {
  items: Notification[];
  offset: number;
  rows: number;
  total: number;
  unread: number;
}

export const uri = () => joinAllUri(parentUri(), 'user');

export const get = (request: UserNotificationsRequest = {}, signal?: AbortSignal) => {
  const params = new URLSearchParams();
  if (request.offset !== undefined) {
    params.set('offset', String(request.offset));
  }
  if (request.rows !== undefined) {
    params.set('rows', String(request.rows));
  }

  return hget<UserNotificationsResponse>(uri(), params, undefined, signal);
};
