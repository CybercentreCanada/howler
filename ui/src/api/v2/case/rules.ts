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

export const post = (caseId: string, ruleData: Partial<Rule>): Promise<Case> => {
  return hpost(uri(caseId), ruleData);
};

export const del = (caseId: string, ruleId: string): Promise<Case> => {
  return hdelete(uri(caseId, ruleId));
};

export const put = (caseId: string, ruleId: string, data: Partial<Rule>): Promise<Case> => {
  return hput(uri(caseId, ruleId), data);
};
