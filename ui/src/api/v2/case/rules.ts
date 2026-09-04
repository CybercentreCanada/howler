// eslint-disable-next-line import/no-cycle
import { hdelete, hpost, hput, joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2/case';

import type { Case } from 'models/entities/generated/Case';
import type { Rule } from 'models/entities/generated/Rule';

export const uri = (caseId: string, ruleId?: string) => {
  if (ruleId) {
    return joinAllUri(parentUri(caseId), 'rules', ruleId);
  }

  return joinAllUri(parentUri(caseId), 'rules');
};

export const post = (caseId: string, ruleData: Partial<Rule>) => {
  return hpost<Case>(uri(caseId), ruleData);
};

export const del = (caseId: string, ruleId: string) => {
  return hdelete<Case>(uri(caseId, ruleId));
};

export const put = (caseId: string, ruleId: string, data: Partial<Rule>) => {
  return hput<Case>(uri(caseId, ruleId), data);
};
