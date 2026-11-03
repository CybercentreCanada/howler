import { hpost, joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2';

export interface AnalyticCommentNotification {
  type: 'analytic_comment';
  recipient: string;
  actor: string;
  analytic_id: string;
  analytic_name: string;
  message: string;
}

export const uri = () => joinAllUri(parentUri(), 'notification', 'notify');

export const notify = (analyticId: string, commenter: string) => {
  return hpost<AnalyticCommentNotification>(uri(), { analytic_id: analyticId, commenter });
};
