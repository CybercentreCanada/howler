import { hdelete, hget, hpost, joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2';
import * as read from 'api/v2/notification/read';

export interface Notification {
  notification_id: string;
  recipient: string;
  resource_id: string;
  resource_type: 'analytic';
  sender: string;
  resource_name: string;
  message: string;
  url_path?: string;
  created: string;
  read: boolean;
}

export interface NotificationsRequest {
  offset?: number;
  rows?: number;
}

export interface NotificationsResponse {
  items: Notification[];
  offset: number;
  rows: number;
  total: number;
  unread: number;
}

export const uri = (id?: string) =>
  id ? joinAllUri(parentUri(), 'notification', id) : joinAllUri(parentUri(), 'notification');

export const get = (request: NotificationsRequest = {}, signal?: AbortSignal) => {
  const params = new URLSearchParams();
  if (request.offset !== undefined) {
    params.set('offset', String(request.offset));
  }
  if (request.rows !== undefined) {
    params.set('rows', String(request.rows));
  }

  return hget<NotificationsResponse>(uri(), params, undefined, signal);
};

export const post = (analyticId: string, commenter: string) => {
  return hpost<Notification | null>(uri(), { analytic_id: analyticId, commenter });
};

export const del = (id: string) => {
  return hdelete(uri(id));
};

export { read };
