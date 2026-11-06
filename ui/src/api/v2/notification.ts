import { hpost, joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2';

export interface AnalyticCommentNotification {
  recipient: string;
  resource_id: string;
  resource_type: 'analytic';
  resource_commenter: string;
  resource_name: string;
  message: string;
}

export const uri = () => joinAllUri(parentUri(), 'notification', 'notify');

export const notify = (analyticId: string, commenter: string) => {
  return hpost<AnalyticCommentNotification>(uri(), { analytic_id: analyticId, commenter });
};
