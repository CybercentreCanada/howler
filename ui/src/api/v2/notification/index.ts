import { hdelete, hpost, joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2';
import * as get from 'api/v2/notification/get';
import * as read from 'api/v2/notification/read';

export interface Notification {
  notification_id: string;
  recipient: string;
  resource_id: string;
  resource_type: 'analytic';
  sender: string;
  resource_name: string;
  message: string;
  url?: string;
  created: string;
  read: boolean;
}

export const uri = (id?: string) =>
  id ? joinAllUri(parentUri(), 'notification', id) : joinAllUri(parentUri(), 'notification');

export const notify = (analyticId: string, commenter: string) => {
  return hpost<Notification | null>(joinAllUri(uri(), 'notify'), { analytic_id: analyticId, commenter });
};

export const del = (id: string) => {
  return hdelete(uri(id));
};

export { get, read };
