import { hpost, joinAllUri } from 'api';
import { uri as caseUri } from 'api/v2/case';
import * as count from './count';

export const uri = (caseId: string, ruleId: string) => {
  return joinAllUri(caseUri(caseId), 'rules', ruleId, 'backfill');
};

export const post = (caseId: string, ruleId: string, since: string) => {
  return hpost<{ queued: number }>(uri(caseId, ruleId), { since });
};

export { count };
