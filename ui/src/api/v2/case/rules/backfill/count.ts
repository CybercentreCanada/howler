import { hpost, joinAllUri } from 'api';
import { uri as caseUri } from 'api/v2/case';

export const uri = (caseId: string, ruleId: string) => {
  return joinAllUri(caseUri(caseId), 'rules', ruleId, 'backfill', 'count');
};

export const post = (caseId: string, ruleId: string, since: string) => {
  return hpost<{ count: number }>(uri(caseId, ruleId), { since });
};
