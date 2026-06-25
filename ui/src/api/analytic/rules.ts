import { hpost, joinUri, type HowlerRefreshParam } from 'api';
import { uri as parentUri } from 'api/analytic';
import type { Analytic } from 'models/entities/generated/Analytic';

export const uri = () => {
  return joinUri(parentUri(), 'rules');
};

export const post = (
  body: Pick<Analytic, 'description' | 'name' | 'rule' | 'rule_type' | 'rule_crontab'>,
  refresh?: HowlerRefreshParam
): Promise<Analytic> => {
  return hpost(uri(), body, undefined, refresh ? new URLSearchParams({ refresh }) : undefined);
};
